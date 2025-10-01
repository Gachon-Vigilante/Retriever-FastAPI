import asyncio
import os
import json
import tempfile
from typing import Sequence, Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, update, and_, func
from sqlalchemy.orm import relationship

from google import genai
from google.genai import types
from pydantic import Field

from core.mongo.post import Post, PostAnalysisResult, TelegramPromotion
from utils import Logger
from ..models import prompts

Base = declarative_base()

logger = Logger(__name__)

class JobStatus(Enum):
    ACCEPTING_REQUESTS = "accepting_requests"  # 새로 추가
    PENDING = "pending"
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AIPostAnalysisResult(PostAnalysisResult):
    drugs_related: bool = Field(
        default=False,
        title="Drugs Detection Result",
        description=prompts["analysis"]["post"]["drugs_related"],
    )


class AITelegramPromotion(TelegramPromotion):
    content: str = Field(
        default="",
        title="Promotion Content",
        description=prompts["analysis"]["post"]["content"],
    )
    links: list[str] = Field(
        default_factory=list,
        title="Promoted Telegram Links",
        description=prompts["analysis"]["post"]["links"],
    )


class GeminiBatchJobs(Base):
    """Gemini 배치 작업 테이블"""
    __tablename__ = 'gemini_batch_jobs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=True)  # Gemini API에서 반환하는 job name
    status = Column(String(50), nullable=False, default=JobStatus.ACCEPTING_REQUESTS.value)
    file_size_bytes = Column(Integer, default=0)  # 파일 크기 추적
    request_count = Column(Integer, default=0)  # 요청 개수 추적
    result = Column(Text, nullable=True)  # 작업 결과 저장
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 관계 설정
    requests = relationship("GeminiRequests", back_populates="batch_job", cascade="all, delete-orphan")


class GeminiRequests(Base):
    """개별 Gemini 요청 테이블"""
    __tablename__ = 'gemini_requests'

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_key = Column(String(100), unique=True, nullable=False, index=True)
    batch_job_id = Column(
        Integer,
        ForeignKey(
            column=GeminiBatchJobs.id,
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
        index=True
    )

    # Post 정보
    post_title = Column(Text, nullable=False)
    post_text = Column(Text, nullable=False)
    post_link = Column(Text, nullable=False)

    # 요청 데이터 (JSON 문자열)
    contents = Column(Text, nullable=False)
    generation_config = Column(Text, nullable=False)
    estimated_size_bytes = Column(Integer, default=0)  # 예상 크기

    # 결과 및 상태
    is_processed = Column(Boolean, default=False, nullable=False)
    result = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.now)

    # 관계 설정
    batch_job = relationship("GeminiBatchJobs", back_populates="requests")

    __table_args__ = (
        Index('idx_gemini_requests_processed', 'is_processed'),
        Index('idx_gemini_requests_batch_job', 'batch_job_id'),
        Index('idx_gemini_requests_batch_status', 'batch_job_id', 'is_processed'),
    )


class PostAnalyzer:
    # 1GB 크기 제한 상수
    MAX_FILE_SIZE_BYTES = 1024 * 1024 * 1024  # 1GB

    def __init__(self, db_path: str = "teleprobe.db"):
        self.db_url = f"sqlite+aiosqlite:///{db_path}"
        self.engine = create_async_engine(self.db_url, echo=False)
        self.async_session = async_sessionmaker(self.engine, expire_on_commit=False)

        self.template: list = [
            {
                "parts": [{"text": prompts["analysis"]["post"]["main"]}],
                "role": "system",
            },
            {
                "parts": [{"text": "Analyze the following webpage:"}],
                "role": "user"
            },
        ]

        self.client = genai.Client()

    async def __aenter__(self):
        """데이터베이스 초기화"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # 초기 accepting_requests Job 생성
        await self._ensure_accepting_requests_job()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.engine.dispose()

    async def _ensure_accepting_requests_job(self):
        """ACCEPTING_REQUESTS 상태의 Job이 정확히 하나만 있도록 보장"""
        async with self.async_session() as session:
            # 기존 ACCEPTING_REQUESTS Job 확인
            result = await session.execute(
                select(GeminiBatchJobs)
                .where(GeminiBatchJobs.status == JobStatus.ACCEPTING_REQUESTS.value)
            )
            accepting_jobs = result.scalars().all()

            if len(accepting_jobs) == 0:
                # 없으면 새로 생성
                new_job = GeminiBatchJobs(
                    status=JobStatus.ACCEPTING_REQUESTS.value,
                    file_size_bytes=0,
                    request_count=0
                )
                session.add(new_job)
                await session.commit()
                print("새로운 Batch Job이 생성되었습니다.")

            elif len(accepting_jobs) > 1:
                # 여러 개 있으면 첫 번째만 남기고 나머지는 PENDING으로 변경
                keep_job = accepting_jobs[0]
                for job in accepting_jobs[1:]:
                    await session.execute(
                        update(GeminiBatchJobs)
                        .where(GeminiBatchJobs.id == job.id)
                        .values(status=JobStatus.PENDING.value)
                    )
                await session.commit()
                print(f"중복된 ACCEPTING_REQUESTS Job들을 정리함. 유지: {keep_job.id}")

    def format(self, post: Post) -> list:
        instruction = (
            "Return a strict JSON object with keys: drugs_related (boolean), promotions (array of objects with keys 'content' and 'links' (array of strings)). "
            "Do not include any text outside of the JSON."
        )
        return self.template + [
            {
                "parts": [{"text": f"{instruction}\n\nTitle: {post.title} \n\nContent: {post.text}"}],
                "role": "user"
            },
        ]

    def _estimate_request_size(self, post: Post) -> int:
        """요청의 예상 크기를 바이트 단위로 계산"""
        contents = json.dumps(self.format(post), ensure_ascii=False)
        generation_config = json.dumps({"temperature": 0.2}, ensure_ascii=False)

        batch_data = {
            "key": f"request-temp",
            "request": {
                "contents": json.loads(contents),
                "generation_config": json.loads(generation_config)
            }
        }

        jsonl_line = json.dumps(batch_data, ensure_ascii=False) + "\n"
        return len(jsonl_line.encode('utf-8'))

    async def _get_accepting_requests_job(self) -> Optional[GeminiBatchJobs]:
        """현재 ACCEPTING_REQUESTS 상태의 Job 가져오기"""
        async with self.async_session() as session:
            result = await session.execute(
                select(GeminiBatchJobs)
                .where(GeminiBatchJobs.status == JobStatus.ACCEPTING_REQUESTS.value)
            )
            return result.scalar_one_or_none()

    async def is_accepting_requests(self) -> bool:
        """새로운 요청을 받을 수 있는 상태인지 확인"""
        accepting_job = await self._get_accepting_requests_job()
        return accepting_job is not None

    async def register(self, post: Post) -> bool:
        """
        배치 요청에 post 등록
        Returns: 등록 성공 여부
        """
        if not await self.is_accepting_requests():
            return False

        async with self.async_session() as session:
            try:
                # 요청 크기 추정
                estimated_size = self._estimate_request_size(post)

                # 중복 확인을 위한 고유 키 생성
                post_hash = hash(f"{post.title}:{post.text}")
                request_key = f"request-{abs(post_hash)}"

                # 이미 존재하는 요청인지 확인
                existing = await session.execute(
                    select(GeminiRequests).where(GeminiRequests.request_key == request_key)
                )
                if existing.scalar_one_or_none():
                    return True  # 이미 등록된 요청

                # 현재 ACCEPTING_REQUESTS Job 가져오기
                result = await session.execute(
                    select(GeminiBatchJobs)
                    .where(GeminiBatchJobs.status == JobStatus.ACCEPTING_REQUESTS.value)
                )
                current_job = result.scalar_one()

                # 1GB 제한 확인
                if (current_job.file_size_bytes + estimated_size) > self.MAX_FILE_SIZE_BYTES:
                    # 현재 Job을 PENDING으로 변경
                    await session.execute(
                        update(GeminiBatchJobs)
                        .where(GeminiBatchJobs.id == current_job.id)
                        .values(status=JobStatus.PENDING.value, updated_at=datetime.now())
                    )

                    # 새로운 ACCEPTING_REQUESTS Job 생성
                    new_job = GeminiBatchJobs(
                        status=JobStatus.ACCEPTING_REQUESTS.value,
                        file_size_bytes=0,
                        request_count=0
                    )

                    session.add(new_job)
                    await session.flush()  # ID 생성을 위해
                    current_job = new_job
                    print(f"1GB 한계 도달. 새 Job {new_job.id} 생성")

                # 요청 데이터 생성
                contents = json.dumps(self.format(post), ensure_ascii=False)
                generation_config = json.dumps({"temperature": 0.2}, ensure_ascii=False)

                # 새 요청 저장
                new_request = GeminiRequests(
                    request_key=request_key,
                    batch_job_id=current_job.id,
                    post_title=post.title,
                    post_text=post.text or "",
                    post_link=post.link,
                    contents=contents,
                    generation_config=generation_config,
                    estimated_size_bytes=estimated_size
                )

                session.add(new_request)

                # Job 크기 및 개수 업데이트
                await session.execute(
                    update(GeminiBatchJobs)
                    .where(GeminiBatchJobs.id == current_job.id)
                    .values(
                        file_size_bytes=current_job.file_size_bytes + estimated_size,
                        request_count=current_job.request_count + 1,
                        updated_at=datetime.now()
                    )
                )

                await session.commit()
                return True

            except Exception as e:
                await session.rollback()
                print(f"등록 실패: {e}")
                return False

    async def submit_batch(self) -> Optional[List[str]]:
        """
        배치 작업 제출 - ACCEPTING_REQUESTS와 PENDING 상태의 모든 Job들을 제출
        Returns: 제출된 배치 작업명 리스트 또는 None (실패시)
        """
        async with self.async_session() as session:
            # 제출할 Job들 가져오기 (ACCEPTING_REQUESTS + PENDING)
            jobs_result = await session.execute(
                select(GeminiBatchJobs)
                .where(
                    and_(
                        GeminiBatchJobs.status.in_([
                            JobStatus.ACCEPTING_REQUESTS.value,
                            JobStatus.PENDING.value
                        ]),
                        GeminiBatchJobs.request_count > 0  # 요청이 있는 Job만
                    )
                )
            )
            jobs_to_submit = jobs_result.scalars().all()

            if not jobs_to_submit:
                print("제출할 작업이 없음")
                return None

            submitted_job_names = []

            for job in jobs_to_submit:
                try:
                    # Job의 요청들 가져오기
                    requests_result = await session.execute(
                        select(GeminiRequests)
                        .where(GeminiRequests.batch_job_id == job.id)
                        .where(GeminiRequests.is_processed == False)
                    )
                    requests = requests_result.scalars().all()

                    if not requests:
                        continue

                    # JSONL 파일 생성
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
                        temp_path = f.name

                        for req in requests:
                            batch_data = {
                                "key": req.request_key,
                                "request": {
                                    "contents": json.loads(req.contents),
                                    "generation_config": json.loads(req.generation_config)
                                }
                            }
                            f.write(json.dumps(batch_data, ensure_ascii=False) + "\n")

                    try:
                        # 파일 업로드
                        uploaded_file = self.client.files.upload(
                            file=temp_path,
                            config=types.UploadFileConfig(
                                display_name=f'batch-job-{job.id}-{datetime.now().strftime("%Y%m%d-%H%M%S")}',
                                mime_type='application/jsonl'
                            )
                        )

                        print(f"파일 업로드됨: {uploaded_file.name}")

                        # 배치 작업 생성
                        batch_job = self.client.batches.create(
                            requests_file=uploaded_file.name,
                            config=types.CreateBatchConfig(
                                model="models/gemini-2.0-flash-exp"
                            )
                        )

                        # Job 상태를 SUBMITTED로 업데이트
                        await session.execute(
                            update(GeminiBatchJobs)
                            .where(GeminiBatchJobs.id == job.id)
                            .values(
                                name=batch_job.name,
                                status=JobStatus.SUBMITTED.value,
                                updated_at=datetime.now()
                            )
                        )

                        submitted_job_names.append(batch_job.name)
                        print(f"배치 작업 제출됨: {batch_job.name}")

                    finally:
                        # 임시 파일 정리
                        if os.path.exists(temp_path):
                            os.unlink(temp_path)

                except Exception as e:
                    print(f"Job {job.id} 제출 실패: {e}")
                    # 개별 Job 실패해도 다른 Job들은 계속 처리
                    await session.execute(
                        update(GeminiBatchJobs)
                        .where(GeminiBatchJobs.id == job.id)
                        .values(status=JobStatus.FAILED.value, updated_at=datetime.now())
                    )
                    continue

            await session.commit()

            # 새로운 ACCEPTING_REQUESTS Job 생성 (모든 Job이 제출된 후)
            await self._ensure_accepting_requests_job()

            return submitted_job_names if submitted_job_names else None

    async def check_batch_status(self) -> Optional[Dict[str, Any]]:
        """배치 작업 상태 확인 및 업데이트. 완료된 경우 결과 처리는 포함하지 않음"""
        async with self.async_session() as session:
            jobs_result = await session.execute(
                select(GeminiBatchJobs)
                .where(
                    and_(
                        GeminiBatchJobs.status.in_([
                            JobStatus.SUBMITTED.value,
                            JobStatus.PROCESSING.value
                        ]),
                        GeminiBatchJobs.name.isnot(None)
                    )
                )
            )
            active_jobs = jobs_result.scalars().all()

            if not active_jobs:
                return None

            job_statuses = []

            for job in active_jobs:
                try:
                    batch_info = self.client.batches.get(job.name)

                    new_status = None
                    if getattr(batch_info, 'state', None) == "COMPLETED":
                        new_status = JobStatus.COMPLETED.value
                    elif getattr(batch_info, 'state', None) in ["FAILED", "CANCELLED"]:
                        new_status = JobStatus.FAILED.value
                    elif getattr(batch_info, 'state', None) == "RUNNING":
                        new_status = JobStatus.PROCESSING.value

                    if new_status and new_status != job.status:
                        await session.execute(
                            update(GeminiBatchJobs)
                            .where(GeminiBatchJobs.id == job.id)
                            .values(status=new_status, updated_at=datetime.now())
                        )

                    job_statuses.append({
                        "job_id": job.id,
                        "name": getattr(batch_info, 'name', job.name),
                        "state": getattr(batch_info, 'state', job.status),
                        "request_count": getattr(batch_info, 'request_count', 0),
                        "processed_count": getattr(batch_info, 'processed_count', 0)
                    })

                except Exception as e:
                    print(f"Job {job.id} 상태 확인 실패: {e}")

            await session.commit()

            return {
                "jobs": job_statuses,
                "total_jobs": len(job_statuses)
            }

    async def get_job_statistics(self) -> Dict[str, Any]:
        """Job 통계 조회"""
        async with self.async_session() as session:
            # 각 상태별 Job 개수
            status_counts = {}
            for status in JobStatus:
                result = await session.execute(
                    select(func.count(GeminiBatchJobs.id))
                    .where(GeminiBatchJobs.status == status.value)
                )
                status_counts[status.value] = result.scalar() or 0

            # 대기 중인 요청 수 (ACCEPTING_REQUESTS + PENDING Job의 요청들)
            pending_requests_result = await session.execute(
                select(func.count(GeminiRequests.id))
                .join(GeminiBatchJobs)
                .where(
                    GeminiBatchJobs.status.in_([
                        JobStatus.ACCEPTING_REQUESTS.value,
                        JobStatus.PENDING.value
                    ])
                )
                .where(GeminiRequests.is_processed == False)
            )
            pending_requests = pending_requests_result.scalar() or 0

            # 처리된 요청 수
            processed_requests_result = await session.execute(
                select(func.count(GeminiRequests.id))
                .where(GeminiRequests.is_processed == True)
            )
            processed_requests = processed_requests_result.scalar() or 0

            return {
                "job_status_counts": status_counts,
                "pending_requests": pending_requests,
                "processed_requests": processed_requests,
                "total_requests": pending_requests + processed_requests
            }

    async def reset_batch(self):
        """배치 상태 리셋 - 모든 Job을 정리하고 새로 시작"""
        async with self.async_session() as session:
            await session.execute(
                update(GeminiBatchJobs)
                .values(status=JobStatus.FAILED.value)
                .where(GeminiBatchJobs.status != JobStatus.COMPLETED.value)
            )
            await session.commit()
            await self._ensure_accepting_requests_job()
            print("배치 상태가 리셋되었습니다.")

    async def process_completed_jobs(self) -> Dict[str, Any]:
        """완료된 배치 작업의 결과를 다운로드 및 파싱하여 MongoDB Post에 저장"""
        processed = {"jobs": 0, "requests": 0}
        async with self.async_session() as session:
            jobs_result = await session.execute(
                select(GeminiBatchJobs)
                .where(GeminiBatchJobs.status == JobStatus.COMPLETED.value)
                .where(GeminiBatchJobs.name.isnot(None))
            )
            completed_jobs = jobs_result.scalars().all()
            if not completed_jobs:
                return processed

            from core.mongo.connections import MongoCollections
            posts_col = MongoCollections().posts

            for job in completed_jobs:
                try:
                    batch_info = self.client.batches.get(job.name)
                    # 다양한 SDK 버전을 대비한 결과 파일 속성 탐색
                    result_file_name = None
                    candidates = [
                        getattr(batch_info, 'result', None),
                        getattr(batch_info, 'results', None),
                        getattr(batch_info, 'output_file', None),
                    ]
                    for c in candidates:
                        if isinstance(c, dict) and 'output_file' in c:
                            result_file_name = c['output_file']
                            break
                        if isinstance(c, str):
                            result_file_name = c
                            break
                        if hasattr(c, 'output_file'):
                            result_file_name = getattr(c, 'output_file')
                            break
                    # 최후 수단: batch_info 자체에 files 속성 검사
                    if not result_file_name and hasattr(batch_info, 'files'):
                        files = getattr(batch_info, 'files')
                        if isinstance(files, list) and files:
                            result_file_name = files[0]

                    if not result_file_name:
                        print(f"Job {job.id} 결과 파일을 찾지 못했습니다.")
                        continue

                    downloaded = self.client.files.download(file=result_file_name)
                    # 다운로드 결과에서 텍스트 추출
                    content_text = getattr(downloaded, 'text', None) or getattr(downloaded, 'content', None)
                    if not isinstance(content_text, str):
                        try:
                            content_text = downloaded.read().decode('utf-8')
                        except Exception:
                            content_text = ""

                    # JSONL 파싱
                    for line in content_text.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                        except Exception:
                            continue

                        req_key = obj.get('key') or obj.get('request', {}).get('key')
                        # 응답 텍스트 추출
                        resp_text = None
                        response = obj.get('response')
                        if response:
                            try:
                                # google genai 응답 구조 가정
                                cands = response.get('candidates') or []
                                if cands:
                                    parts = cands[0].get('content', {}).get('parts', [])
                                    if parts:
                                        resp_text = parts[0].get('text')
                            except Exception:
                                pass
                        if not resp_text and 'error' in obj:
                            resp_text = json.dumps(obj['error'], ensure_ascii=False)
                        if resp_text is None:
                            continue

                        # GeminiRequests 업데이트
                        req_row_result = await session.execute(
                            select(GeminiRequests).where(GeminiRequests.request_key == req_key)
                        )
                        req_row = req_row_result.scalar_one_or_none()
                        if not req_row:
                            continue
                        await session.flush()
                        req_row.result = resp_text
                        req_row.is_processed = True

                        # 분석 결과 파싱(JSON 기대)
                        analysis_dict = None
                        try:
                            analysis_dict = json.loads(resp_text)
                        except Exception:
                            # 비 JSON 응답은 건너뜀
                            analysis_dict = None

                        if analysis_dict and isinstance(analysis_dict, dict):
                            # MongoDB 업데이트
                            try:
                                update_fields = {"analysis": analysis_dict}
                                try:
                                    # 판매글일 경우 본문을 함께 저장
                                    if isinstance(analysis_dict.get("drugs_related"), bool) and analysis_dict.get("drugs_related"):
                                        update_fields["text"] = req_row.post_text or ""
                                    else:
                                        # 판매글이 아닌 경우 본문은 저장하지 않도록 명시적으로 제거 가능 (선택)
                                        update_fields["text"] = None
                                except Exception:
                                    pass
                                posts_col.update_one(
                                    {"link": req_row.post_link},
                                    {"$set": update_fields},
                                    upsert=False,
                                )
                            except Exception as e:
                                print(f"MongoDB 업데이트 실패: {e}")
                        processed["requests"] += 1

                    processed["jobs"] += 1

                except Exception as e:
                    print(f"Job {job.id} 결과 처리 실패: {e}")
            await session.commit()
        return processed