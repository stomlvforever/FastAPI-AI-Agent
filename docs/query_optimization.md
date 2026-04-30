# 查询优化指南 (Query Optimization Guide)

## 一、已添加的索引清单

| 表 | 索引名 | 列 | 优先级 | 用途 |
|---|---|---|---|---|
| items | ix_items_owner_id | owner_id | 🔴高 | WHERE owner_id=? 查询 |
| items | ix_items_created_at | created_at | 🟡中 | ORDER BY created_at 排序 |
| comments | ix_comments_item_id | item_id | 🔴高 | WHERE item_id=? 查询 |
| comments | ix_comments_author_id | author_id | 🟡中 | 级联删除 + 反向查询 |
| comments | ix_comments_created_at | created_at | 🟡中 | ORDER BY created_at 排序 |
| favorites | ix_favorites_article_id | article_id | 🔴高 | COUNT(WHERE article_id=?) 子查询 |
| followers | ix_followers_following_id | following_id | 🔴高 | get_followers JOIN + Feed |
| articles | ix_articles_created_at | created_at | 🟡中 | 文章列表/Feed 默认排序 |
| item_tags | ix_item_tags_tag_id | tag_id | 🟢低 | 某 tag 下的所有 items |
| article_tags | ix_article_tags_tag_id | tag_id | 🟢低 | 某 tag 下的所有 articles |

---

## 二、关键 SQL 与 EXPLAIN 分析

### 2.1 文章列表（高频查询）

```sql
-- 对应 ArticleRepository.get_articles()
-- 验证命令（在 psql 或 pgAdmin 中执行）：
EXPLAIN ANALYZE
SELECT a.*, COUNT(f.article_id) AS favorites_count
FROM articles a
LEFT JOIN favorites f ON f.article_id = a.id
WHERE a.author_id = 1                   -- 走 ix_articles_author_id
GROUP BY a.id
ORDER BY a.created_at DESC              -- 走 ix_articles_created_at
LIMIT 20 OFFSET 0;
```

**优化前**（无 article_id 索引）：`favorites` 表做 Seq Scan，O(n) 全表扫描
**优化后**（有 ix_favorites_article_id）：Index Scan，O(log n)

### 2.2 某个 Item 的评论列表

```sql
-- 对应 CommentRepository.get_comments_by_item()
EXPLAIN ANALYZE
SELECT * FROM comments
WHERE item_id = 1                       -- 走 ix_comments_item_id
ORDER BY created_at ASC;                -- 走 ix_comments_created_at
```

**优化前**：全表扫描 comments
**优化后**：Index Scan on ix_comments_item_id

### 2.3 用户 Feed（关注者的文章）

```sql
-- 对应 ArticleRepository.get_feed()
EXPLAIN ANALYZE
SELECT a.*
FROM articles a
INNER JOIN followers f
    ON f.following_id = a.author_id     -- 走 ix_followers_following_id
WHERE f.follower_id = 1                 -- 走 PK 左前缀
ORDER BY a.created_at DESC
LIMIT 20;
```

**优化前**：followers 上 following_id 是联合 PK 第二列，单独 JOIN 无法走索引
**优化后**：走 ix_followers_following_id，再通过 NestLoop 匹配 articles

### 2.4 用户的 Item 列表

```sql
-- 对应 ItemRepository.get_items_by_user()
EXPLAIN ANALYZE
SELECT * FROM items
WHERE owner_id = 1                      -- 走 ix_items_owner_id
  AND status = 'pending'                -- 附加过滤
ORDER BY priority ASC, created_at DESC
LIMIT 20;
```

---

## 三、EXPLAIN 使用技巧

### 基本用法
```sql
-- 只看执行计划（不实际执行）
EXPLAIN SELECT ...;

-- 实际执行并显示耗时（推荐）
EXPLAIN ANALYZE SELECT ...;

-- 显示更多细节（buffers、I/O 等）
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) SELECT ...;
```

### 关键指标解读

| 指标 | 含义 | 优化目标 |
|---|---|---|
| Seq Scan | 全表扫描 | ❌ 应该被 Index Scan 替代 |
| Index Scan | 索引扫描 | ✅ 理想状态 |
| Index Only Scan | 仅索引扫描 | ✅✅ 最佳（不回表） |
| Bitmap Index Scan | 位图索引 | ⚠️ 还行，适合中等选择性 |
| Sort | 内存排序 | ⚠️ 检查是否可以用索引避免 |
| actual time | 实际耗时（ms） | 越小越好 |
| rows | 预估/实际行数 | 差距大 = 统计信息过时 |

### 常见问题排查

```sql
-- 1. 查看表的索引情况
SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'items';

-- 2. 查看表的统计信息是否过时
SELECT relname, last_analyze, last_autoanalyze
FROM pg_stat_user_tables
WHERE relname = 'items';

-- 3. 手动更新统计信息（加索引后建议执行一次）
ANALYZE items;
ANALYZE comments;
ANALYZE favorites;
ANALYZE followers;
ANALYZE articles;

-- 4. 查看索引使用情况
SELECT indexrelname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
WHERE relname = 'items';
```

---

## 四、PostgreSQL 索引注意事项

### 🚨 PostgreSQL 不会自动为 FK 创建索引！
这是与 MySQL/InnoDB 最大的差异。每个外键列如果需要高效查询，**必须手动添加索引**。

### 🚨 联合主键的"左前缀"规则
联合主键 `(a, b)` 只对 `WHERE a=?` 或 `WHERE a=? AND b=?` 走索引。
`WHERE b=?` **无法使用**此索引，需要单独为 `b` 建索引。

### ✅ 最佳实践
1. 每个 FK 列加 `index=True`
2. 高频排序列 (`ORDER BY created_at`) 加索引
3. 联合 PK 关联表：为第二列添加单独索引
4. 加索引后执行 `ANALYZE <table>` 更新统计信息
5. 定期检查 `pg_stat_user_indexes` 确认索引被使用
