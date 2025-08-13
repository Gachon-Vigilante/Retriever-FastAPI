from core.mongo.schemas import Post


class PostHandler:
    def __init__(self):
        pass

    async def __call__(self, post: Post):
        post.store()
