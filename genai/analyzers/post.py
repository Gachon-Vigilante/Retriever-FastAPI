import json
import os
import tempfile
from datetime import datetime
from enum import StrEnum
from typing import Optional, Dict, Any, List

from bson import ObjectId
from google import genai
from google.genai import types
from google.genai.types import CreateBatchJobConfig, GenerationConfig
from pydantic import Field, ValidationError, BaseModel

from core.mongo.connections import MongoCollections
from core.mongo.post import Post, PostAnalysisResult, TelegramPromotion, PostFields
from utils import Logger
from ..models import prompts

logger = Logger(__name__)

class JobStatus(StrEnum):
    ACCEPTING_REQUESTS = "accepting_requests"  # 새로 추가
    PENDING = "pending"
    SUBMITTED = "submitted"
    PROCESSED = "processed" # gemini에서는 성공했지만 다운로드 후 반영하지는 않은 상태
    COMPLETED = "completed"
    FAILED = "failed"

class GeminiBatchJobState(StrEnum):
    PENDING = "JOB_STATE_PENDING"
    RUNNING = "JOB_STATE_RUNNING"
    SUCCEEDED = "JOB_STATE_SUCCEEDED"
    FAILED = "JOB_STATE_FAILED"
    CANCELLED = "JOB_STATE_CANCELLED"
    EXPIRED = "JOB_STATE_EXPIRED"

class JobCompletionResult(BaseModel):
    message: str = Field(
        default="completed all AI processed jobs.",
        title="Message",
        description="The message that was returned by the job completion.",
    )
    processed_job_count: int = Field(
        default=0,
        title="Processed Job Count",
        description="The number of jobs that were processed in AI successfully.",
    )
    completed_job_count: int = Field(
        default=0,
        title="Completed Job Count",
        description="The number of jobs that were completed successfully.",
    )
    completed_request_count: int = Field(
        default=0,
        title="Completed Request Count",
        description="The number of requests that were completed successfully.",
    )
    telegram_channel_keys: list[str] = Field(
        default=[],
        title="Telegram Channel Keys",
    )


class PostAnalyzer:
    # 1GB 크기 제한 상수
    MAX_FILE_SIZE_BYTES = 1024 * 1024 * 1024  # 1GB

    def __init__(self):
        self.collections = MongoCollections()
        self.template: list = [
            {
                "parts": [{"text": prompts["analysis"]["post"]["main"]}],
                "role": "user",
            },
            {
                "parts": [{"text": "Analyze the following webpage:"}],
                "role": "user"
            },
        ]
        self.client = genai.Client()
        self.generation_config: dict = {
            "temperature": 0.1,
            "response_mime_type": "application/json",
            "response_json_schema": PostAnalysisResult.gemini_compatible_schema()
        }


    async def __aenter__(self):
        """MongoDB 초기화: ACCEPTING_REQUESTS Job 보장"""
        await self._ensure_accepting_requests_job()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    async def _ensure_accepting_requests_job(self):
        """Ensure exactly one ACCEPTING_REQUESTS job exists in MongoDB."""
        jobs_col = self.collections.analysis_jobs
        accepting = list(jobs_col.find({"status": JobStatus.ACCEPTING_REQUESTS}))
        if len(accepting) == 0:
            jobs_col.insert_one({
                "name": None,
                "status": JobStatus.ACCEPTING_REQUESTS,
                "file_size_bytes": 0,
                "post_count": 0,
                "result": None,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            })
        elif len(accepting) > 1:
            keep_id = accepting[0]["_id"]
            jobs_col.update_many(
                {"_id": {"$ne": keep_id}, "status": JobStatus.ACCEPTING_REQUESTS},
                {"$set": {"status": JobStatus.PENDING, "updated_at": datetime.now()}}
            )

    def format(self, post: Post) -> list:
        instruction = (
            "Return a strict JSON object with keys: drugs_related (boolean), promotions (array of objects with keys 'content' and 'identifiers' (array of strings)). "
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
        batch_data = {
            "key": f"request-temp",
            "request": {
                "contents": self.format(post),
                "generation_config": self.generation_config
            }
        }

        jsonl_line = json.dumps(batch_data, ensure_ascii=False,) + "\n"
        return len(jsonl_line.encode('utf-8'))

    async def _get_accepting_requests_job(self) -> Optional[Dict[str, Any]]:
        """현재 ACCEPTING_REQUESTS 상태의 Job 가져오기 (Mongo)"""
        return self.collections.analysis_jobs.find_one({"status": JobStatus.ACCEPTING_REQUESTS.value})

    async def is_accepting_requests(self) -> bool:
        """새로운 요청을 받을 수 있는 상태인지 확인"""
        accepting_job = await self._get_accepting_requests_job()
        return accepting_job is not None

    async def register(self, post_id: str) -> bool:
        """
        배치 요청에 post 등록 (MongoDB)
        Returns: 등록 성공 여부
        """
        if not await self.is_accepting_requests():
            return False

        posts_collection = self.collections.posts
        jobs_collection = self.collections.analysis_jobs
        post: Post = Post.from_mongo(posts_collection.find_one({"_id": ObjectId(post_id)}))
        # post에 HTML 태그를 제외하고 유의미한 텍스트가 없을 때에는 생략
        if not post.text:
            logger.warning(f"게시글에서 유의미한 텍스트가 발견되지 않았습니다. Post ID: {post_id}")
            return False

        # 요청 크기 추정
        estimated_size = self._estimate_request_size(post)

        # 현재 ACCEPTING_REQUESTS Job 가져오기
        current_job = jobs_collection.find_one({"status": JobStatus.ACCEPTING_REQUESTS})
        if not current_job:
            await self._ensure_accepting_requests_job()
            current_job = jobs_collection.find_one({"status": JobStatus.ACCEPTING_REQUESTS})
        if not current_job:
            return False

        # 1GB 제한 확인
        if int(current_job.get("file_size_bytes", 0)) + estimated_size > self.MAX_FILE_SIZE_BYTES:
            jobs_collection.update_one(
                {"_id": current_job["_id"]},
                {"$set": {"status": JobStatus.PENDING, "updated_at": datetime.now()}}
            )
            # 새 Job 생성
            jobs_collection.insert_one({
                "name": None,
                "post_count": 0,
                "status": JobStatus.ACCEPTING_REQUESTS,
                "file_size_bytes": 0,
                "result": None,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            })
            current_job = jobs_collection.find_one({"status": JobStatus.ACCEPTING_REQUESTS})

        # post의 analysis job id 필드를 현재 작업 id로 설정
        # analysis_job_id가 현재 작업의 ID가 아닌 경우에만 원자적 업데이트
        result = posts_collection.update_one(
            {
                "_id": ObjectId(post_id),
                "text": {"$ne": None},
                "analysis": None,
                "analysis_job_id": {"$ne": current_job["_id"]},
            },
            {
                "$set": {"analysis_job_id": current_job["_id"]},
            }
        )
        # 실제로 업데이트된 경우에만 카운트 증가
        if result.modified_count > 0:
            # Job 크기, 개수 업데이트
            jobs_collection.update_one(
                {"_id": current_job["_id"]},
                {
                    "$inc": {"file_size_bytes": int(estimated_size), "post_count": 1},
                    "$set": {"updated_at": datetime.now()},
                }
            )
            logger.info(f"게시글을 작업에 등록했습니다. Post ID: {post_id}, Job ID: {current_job['_id']}")
        else:
            logger.warning(f"이미 등록되어 있거나 조건에 맞지 않는 게시글입니다. Post ID: {post_id}")
            return False

        return True

    async def register_all(self):
        posts_collection = self.collections.posts
        analysis_jobs_collection = self.collections.analysis_jobs

        posts_to_analyze = list(posts_collection.find({
            "text": {"$nin": [None, ""]},
            "analysis": {"$nin": [None, ""]},
            "analysis_job_id": {"$nin": [
                job["_id"]
                for job in analysis_jobs_collection.find(
                    {"status": {"$in": [JobStatus.ACCEPTING_REQUESTS, JobStatus.PENDING]}},
                )
            ]}
        }))
        for doc in posts_to_analyze:
            await self.register(doc["_id"])

    async def submit_batch(self) -> Optional[List[str]]:
        """
        배치 작업 제출 - ACCEPTING_REQUESTS와 PENDING 상태의 모든 Job들을 제출 (Mongo)
        Returns: 제출된 배치 작업명 리스트 또는 None (실패시)
        """
        posts_collection = self.collections.posts
        analysis_jobs_collection = self.collections.analysis_jobs

        jobs_to_submit = list(analysis_jobs_collection.find({
            "status": {"$in": [JobStatus.ACCEPTING_REQUESTS.value, JobStatus.PENDING.value]},
            "post_count": {"$gt": 0}
        }))
        if not jobs_to_submit:
            return None

        logger.info(f"제출하지 않은 작업 {len(jobs_to_submit)}개가 발견되었습니다.")

        submitted_job_names: list[str] = []
        for job in jobs_to_submit:
            try:
                post_docs = list(posts_collection.find({
                    "text": {"$ne": None},
                    "analysis": None,
                    "analysis_job_id": job["_id"],
                }))
                if not post_docs:
                    continue

                with tempfile.NamedTemporaryFile(
                    mode='w',
                    suffix='.jsonl',
                    delete=False,
                    encoding='utf-8'
                ) as f:
                    temp_path = f.name
                    for doc in post_docs:
                        post = Post.from_mongo(doc)
                        batch_data = {
                            "key": str(doc["_id"]),
                            "request": {
                                "contents": self.format(post),
                                "generation_config": self.generation_config
                            }
                        }
                        f.write(json.dumps(batch_data, ensure_ascii=False) + "\n")
                try:
                    job_id = str(job["_id"])[:8]
                    current_time = datetime.now().strftime("%Y%m%d-%H%M%S")
                    uploaded_file = self.client.files.upload(
                        file=temp_path,
                        config=types.UploadFileConfig(
                            display_name=f"file-{job_id}-{current_time}",
                            mime_type="jsonl"
                        )
                    )
                    batch_job = self.client.batches.create(
                        model="gemini-2.5-flash",
                        src=uploaded_file.name,
                        config=CreateBatchJobConfig(
                            display_name=f"batch-job-{job_id}-{current_time}"
                        ),
                    )
                    analysis_jobs_collection.update_one(
                        {"_id": job["_id"]},
                        {"$set": {"name": batch_job.name, "status": JobStatus.SUBMITTED, "updated_at": datetime.now()}}
                    )
                    submitted_job_names.append(batch_job.name)
                    job["name"] = batch_job.name
                finally:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
            except Exception as e:
                logger.error(f"작업 제출 실패. Job name: {job.get('name')}, Job ID: {job.get('_id')}  error:{e}")
                analysis_jobs_collection.update_one(
                    {"_id": job["_id"]},
                    {"$set": {"status": JobStatus.FAILED, "updated_at": datetime.now()}}
                )
                continue
            else:
                logger.info(f"작업이 제출되었습니다. Job name: {job.get('name')}, Job ID: {job.get('_id')}")

        await self._ensure_accepting_requests_job()
        return submitted_job_names if submitted_job_names else None

    async def check_batch_status(self) -> None:
        """배치 작업 상태 확인 및 업데이트. 완료된 경우 결과 처리는 포함하지 않음 (Mongo)"""
        jobs_col = self.collections.analysis_jobs
        active_jobs = list(jobs_col.find({
            "status": JobStatus.SUBMITTED,
            "name": {"$ne": None}
        }))
        if not active_jobs:
            return None

        for job in active_jobs:
            try:
                batch_info = self.client.batches.get(name=job["name"]) if job.get("name") else None
                if batch_info is None:
                    logger.warning(f"MongoDB에 저장된 배치 작업이 gemini batch 대기열에 없습니다. job id: {job.get('_id')}")
                    continue

                state = batch_info.state.name
                new_status = None
                match state:
                    case GeminiBatchJobState.SUCCEEDED:
                        logger.info(f"배치 작업이 gemini에서 성공했습니다. Job ID: {job.get('_id')}, Job name: {job.get('name')}")
                        new_status = JobStatus.PROCESSED
                    case GeminiBatchJobState.FAILED:
                        logger.warning(f"배치 작업이 gemini에서 실패했습니다. Job ID: {job.get('_id')}, Job name: {job.get('name')}")
                        new_status = JobStatus.FAILED
                    case GeminiBatchJobState.CANCELLED:
                        logger.warning(f"배치 작업이 gemini에서 취소되었습니다. Job ID: {job.get('_id')}, Job name: {job.get('name')}")
                        new_status = JobStatus.FAILED
                    case GeminiBatchJobState.EXPIRED:
                        logger.warning(f"배치 작업이 gemini에서 만료되었습니다. Job ID: {job.get('_id')}, Job name: {job.get('name')}")
                        new_status = JobStatus.FAILED
                    case GeminiBatchJobState.PENDING:
                        logger.info(f"배치 작업이 gemini에서 대기 중입니다. Job ID: {job.get('_id')}, Job name: {job.get('name')}")
                    case GeminiBatchJobState.RUNNING:
                        logger.info(f"배치 작업이 gemini에서 작업 중입니다. Job ID: {job.get('_id')}, Job name: {job.get('name')}")
                    case _:
                        logger.warning(f"배치 작업이 알 수 없는 상태에 있습니다. state: {state}, Job ID: {job.get('_id')}, Job name: {job.get('name')}")

                if new_status:
                    jobs_col.update_one(
                        {"_id": job["_id"]},
                        {"$set": {"status": new_status, "updated_at": datetime.now()}}
                    )
            except Exception as e:
                logger.error(f"Job {job.get('_id')} 상태 확인 실패: {e}")

        return None

    async def get_job_statistics(self) -> Dict[str, Any]:
        """Job 통계 조회 (Mongo)"""
        jobs_col = self.collections.analysis_jobs
        req_col = self.collections.gemini_requests
        # 상태별 Job 개수
        status_counts: Dict[str, int] = {}
        for status in JobStatus:
            status_counts[status.value] = jobs_col.count_documents({"status": status.value})
        # 대기 중인 요청 수: accepting + pending, 미처리
        pending_job_ids = [j["_id"] for j in jobs_col.find({"status": {"$in": [JobStatus.ACCEPTING_REQUESTS.value, JobStatus.PENDING.value]}})]
        pending_requests = req_col.count_documents({"batch_job_id": {"$in": pending_job_ids} , "is_processed": False}) if pending_job_ids else 0
        processed_requests = req_col.count_documents({"is_processed": True})
        return {
            "job_status_counts": status_counts,
            "pending_requests": pending_requests,
            "processed_requests": processed_requests,
            "total_requests": pending_requests + processed_requests,
        }

    async def reset_batch(self):
        """배치 상태 리셋 - 모든 Job을 정리하고 새로 시작 (Mongo)"""
        jobs_col = self.collections.analysis_jobs
        jobs_col.update_many(
            {"status": {"$ne": JobStatus.COMPLETED}},
            {"$set": {"status": JobStatus.FAILED, "updated_at": datetime.now()}}
        )
        await self._ensure_accepting_requests_job()
        logger.info("배치 작업 상태가 모두 초기화되었습니다.")

    async def complete_jobs(self) -> JobCompletionResult:
        """완료된 배치 작업의 결과를 다운로드 및 파싱하여 MongoDB Post에 저장 (Mongo)"""
        job_completion_result = JobCompletionResult()
        jobs_col = self.collections.analysis_jobs
        posts_col = self.collections.posts

        processed_jobs = list(jobs_col.find({"status": JobStatus.PROCESSED, "name": {"$ne": None}}))
        if not processed_jobs:
            logger.info("Gemini에서 처리 완료되어 그 상태가 MongoDB에 반영된 작업이 없습니다.")
            return job_completion_result
        job_completion_result.processed_job_count = len(processed_jobs)
        logger.info(f"Gemini에서 처리가 완료된 작업 {job_completion_result.processed_job_count}개가 발견되었습니다.")

        for job in processed_jobs:
            batch_info = self.client.batches.get(name=job.get("name")) if job.get("name") else None
            if batch_info is None:
                logger.warning(f"MongoDB에 gemini 작업 성공으로 표시된 배치 작업이 gemini batch 대기열에 없습니다. job id: {job.get('_id')}")
                continue
            elif not batch_info.dest or not batch_info.dest.file_name:
                logger.warning(f"Gemini batch 대기열에서 찾은 배치 작업에서 파일이 존재하지 않습니다. job id: {job.get('_id')}")
                continue

            # If a batch job was created with a file, Results are in a file
            result_file_name = batch_info.dest.file_name
            logger.info(f"배치 작업 이름: {job.get("name")}, 결과 파일 이름: {result_file_name} 다운로드 중...")
            file_content = self.client.files.download(file=result_file_name)
            # Process file_content (bytes) as needed
            result_text = file_content.decode('utf-8')

            result_lines = result_text.splitlines()
            for line in result_lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    response = json.loads(line)
                except Exception as e:
                    logger.error(f"결과가 jsonl 형태가 아닙니다. result line: {line}, error: {e}")
                    continue

                if not response:
                    logger.warning("Gemini의 응답 jsonl 파일에서 비어 있는 줄이 발견되었습니다.")
                    continue
                key = self.safe_get(response, "key")
                analysis = self.safe_get(response, "response", "candidates", 0, "content", "parts", 0, "text")
                posts_col.update_one(
                    {"_id": ObjectId(key)},
                    {"$set": {
                        # PostFields.analysis_job_id: None,
                        PostFields.updated_at: datetime.now()
                    }}
                )
                try:
                    analysis_dict = json.loads(analysis)
                    if not isinstance(analysis_dict, dict):
                        raise TypeError(f"Expected dict, got {type(analysis_dict)} instead.")
                except Exception as e:
                    logger.error(f"Gemini의 응답이 변환 가능한 json dictionary 형태가 아닙니다. "
                                 f"result line: {line}, response text: {response}, error: {e}")
                    continue

                try:
                    post_analysis_result = PostAnalysisResult.model_validate(analysis_dict)
                except ValidationError as e:
                    logger.error(f"Gemini의 분석 결과가 응답 스키마에 맞지 않습니다. "
                                 f"result line: {line}, response text: {response}, error: {e}")
                    continue

                posts_col.update_one(
                    {"_id": ObjectId(key)},
                    {"$set": {
                        PostFields.analysis: post_analysis_result.model_dump(),
                        PostFields.updated_at: datetime.now()
                    }}
                )
                job_completion_result.completed_request_count += 1

            jobs_col.update_one(
                {"_id": job["_id"]},
                {"$set": {"status": JobStatus.COMPLETED, "updated_at": datetime.now()}}
            )
            job_completion_result.completed_job_count += 1

        return job_completion_result

    @staticmethod
    def safe_get(data: dict, *keys, default=None):
        """중첩된 딕셔너리에서 안전하게 값을 가져오는 메서드"""
        original_data = data.copy()
        for idx, key in enumerate(keys):
            if isinstance(data, dict) and data.get(key):
                data = data[key]
            elif isinstance(key, int) and isinstance(data, list) and len(data) > key:
                data = data[key]
            else:
                logger.error(f"Gemini가 반환한 응답에 {'.'.join(keys[:idx+1])}가 없습니다. Response line: {original_data}")
                return default
        return data
