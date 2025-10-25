"""클러스터링 라우터 패키지

이 모듈은 게시글/채널의 임베딩·유사도 계산·클러스터링 관련 엔드포인트를
하나의 루트(/clustering) 아래로 묶어 제공합니다. 운영 경로에서는 주로 배치/오프라인
분석에 활용되며, 대량 연산이 수행될 수 있으므로 실서비스 트래픽과 분리하여 사용하세요.

제공 라우트:
- /clustering/preprocess, /similarity, /generate-separate-embeddings, /new-post-similarity,
  /cluster-hdbscan, /cluster-custom (routes.clustering.post)
- /clustering/similarity, /new-channel-similarity (routes.clustering.channel)

주의:
- 본 엔드포인트들은 모델 로드 및 대량 연산으로 인해 시간이 오래 걸릴 수 있습니다.
- 기능 변경 없이 문서화만 추가되었습니다.
"""
from fastapi import APIRouter
from .post import router as post_router

router = APIRouter(prefix="/clustering", tags=["clustering"]) 

router.include_router(post_router)
