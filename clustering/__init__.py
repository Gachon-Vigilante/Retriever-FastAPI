from flask import Blueprint, jsonify, Response
from .channel import calculate_and_store_channel_similarity
from .channel_come_in import calculate_similarity_for_new_channels
from .post_similarity import similarity, embeddings, generate_separate_embeddings
from .post import perform_clustering_with_HDBSCAN, cluster_with_custom_metric

# Blueprint 설정
cluster_bp = Blueprint('cluster', __name__, url_prefix='/cluster')


# '/post_similarity.py' 엔드포인트
@cluster_bp.route('/post_preprocess', methods=['POST'])
def post_preprocess():
    try:
        emb_result = generate_separate_embeddings()

        return jsonify(emb_result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# '/post_similarity.py' 엔드포인트
@cluster_bp.route('/post_similarity', methods=['POST'])
def post_similarity():
    try:
        sim_result = similarity()

        return jsonify(sim_result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
# '/channel.py' 엔드포인트
@cluster_bp.route('/channels', methods=['POST'])
def calculate_similarity():
    result = calculate_and_store_channel_similarity()
    return jsonify(result), 200

# '/channel_come_in.py' 엔드포인트
@cluster_bp.route('/channel_update', methods=['POST'])
def update_new_channel():
    result = calculate_similarity_for_new_channels()
    return jsonify(result), 200

# '/post.py' 엔드포인트

@cluster_bp.route('/post_cluster', methods=['POST'])
def post_clustering():
    try:
        # UMAP 설정을 정의
        umap_configs = {
            'doc': {'n_neighbors': 15, 'n_components': 50, 'metric': 'cosine', 'min_dist': 0.0, 'random_state': 42},
            'keyword': {'n_neighbors': 15, 'n_components': 30, 'metric': 'cosine', 'min_dist': 0.0, 'random_state': 42},
            'price': {'n_neighbors': 10, 'n_components': 15, 'metric': 'cosine', 'min_dist': 0.0, 'random_state': 42
            }

        }
        
        result = cluster_with_custom_metric(
            umap_params=umap_configs,
            weights={'doc': 0.7, 'price': 0.1, 'keyword': 0.2},
            hdbscan_params={'min_cluster_size': 10, 'min_samples': 5}
        )
        
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

