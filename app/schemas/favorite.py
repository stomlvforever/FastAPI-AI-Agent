"""收藏相关 Pydantic Schema。

收藏操作返回受影响的文章，因此复用文章公开响应结构。"""

from app.schemas.article import ArticlePublic


class FavoriteArticleResponse(ArticlePublic):
    pass
