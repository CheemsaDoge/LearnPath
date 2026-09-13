from app.zhihu.hot import parse_hot_list
from app.zhihu.models import classify_zhihu_url
from app.zhihu.reader import parse_reader_response
from app.zhihu.search import normalize_hits, parse_bing_rss, parse_brave_html
from app.zhihu.models import SearchHit


def test_classify_urls():
    assert classify_zhihu_url("https://www.zhihu.com/question/1/answer/2?utm=x") == ("answer", "https://www.zhihu.com/question/1/answer/2")
    assert classify_zhihu_url("https://zhuanlan.zhihu.com/p/48508221") == ("article", "https://zhuanlan.zhihu.com/p/48508221")
    assert classify_zhihu_url("https://www.zhihu.com/question/20691338/") == ("question", "https://www.zhihu.com/question/20691338")
    assert classify_zhihu_url("https://www.zhihu.com/topic/19553176") is None
    assert classify_zhihu_url("https://example.com/question/1") is None


def test_normalize_dedupes_and_filters():
    hits = [
        SearchHit(url="https://zhuanlan.zhihu.com/p/1?x=1", title="a"),
        SearchHit(url="https://zhuanlan.zhihu.com/p/1", title="dup"),
        SearchHit(url="https://www.zhihu.com/people/x", title="profile"),
        SearchHit(url="https://www.zhihu.com/question/9", title="q"),
    ]
    out = normalize_hits(hits, limit=5)
    assert [h.url for h in out] == ["https://zhuanlan.zhihu.com/p/1", "https://www.zhihu.com/question/9"]
    assert out[0].kind == "article" and out[1].kind == "question"


def test_parse_brave_html():
    page = (
        '<div class="snippet svelte-x" data-pos="0" data-type="web" data-keynav="true"><div><a href="https://zhuanlan.zhihu.com/p/115571464" class="l1">'
        '<div class="title search-snippet-title line-clamp-1 svelte-y">深度学习 | 反向传播详解 - 知乎</div></a>'
        '<div class="generic-snippet svelte-z">损失对参数梯度的反向传播可以被这样直观解释</div></div></div>'
        '<div class="snippet svelte-x" data-pos="1" data-type="web"><a href="https://www.zhihu.com/question/1"><div class="title svelte-y">Q - 知乎</div></a></div></section>'
    )
    hits = parse_brave_html(page)
    assert len(hits) == 2
    assert hits[0].title == "深度学习 | 反向传播详解"
    assert "直观解释" in hits[0].snippet


def test_parse_bing_rss():
    xml = "<rss><channel><item><title>T - 知乎</title><link>https://zhuanlan.zhihu.com/p/2</link><description>d &amp; e</description></item></channel></rss>"
    hits = parse_bing_rss(xml)
    assert hits[0].url == "https://zhuanlan.zhihu.com/p/2" and hits[0].title == "T" and hits[0].snippet == "d & e"


def test_reader_parse_blocks_verification_page():
    body = "Title: 安全验证 - 知乎\n\nURL Source: https://www.zhihu.com/question/1\n\nMarkdown Content:\n系统监测到您的网络环境存在异常，请点击下方验证按钮进行验证。"
    page = parse_reader_response("https://www.zhihu.com/question/1", body)
    assert page.ok is False


def test_reader_parse_article():
    body = "Title: 详解Transformer - 知乎\n\nURL Source: https://zhuanlan.zhihu.com/p/1\n\nMarkdown Content:\n![Image 1](https://x/y.png)\n\n[关注](https://www.zhihu.com/signin?next=1)\n\n## 先导知识\n\n正文内容 [Attention](https://zhuanlan.zhihu.com/p/2)。\n\n赞同 2,345"
    page = parse_reader_response("https://zhuanlan.zhihu.com/p/1", body)
    assert page.ok and page.title == "详解Transformer"
    assert "先导知识" in page.text and "Image 1" not in page.text and "signin" not in page.text
    assert "正文内容 Attention。" in page.text
    assert page.votes == 2345


def test_parse_hot_list():
    payload = {"data": [{"detail_text": "935 万热度", "target": {"id": 1, "title": "标题", "url": "https://api.zhihu.com/questions/1", "excerpt": "e", "answer_count": 3, "follower_count": 4}}]}
    items = parse_hot_list(payload)
    assert items[0]["url"] == "https://www.zhihu.com/question/1" and items[0]["heat"] == "935 万热度"


def test_parse_so360_html():
    from app.zhihu.search import parse_so360_html

    page = (
        '<ul><li class="res-list"><h3 class="res-title " ><a href="https://www.so.com/link?m=x" data-mdurl="https://www.zhihu.com/question/501077471/answer/2402307191">吴恩达深度学习<em>直观理解反向传播</em> - 知乎</a></h3>'
        '<p class="res-desc"><span class="gray">2022年3月22日&nbsp;-&nbsp;</span>本文主要讲述<em>反向传播</em>算法</p></li>'
        '<li class="res-list"><h3 class="res-title"><a href="https://ai.so.com/search/x">AI 回答</a></h3><p class="res-desc">无原始链接</p></li>'
        '<li class="res-list"><h3 class="res-title"><a href="https://www.so.com/link?m=y" data-mdurl="https://www.zhihu.com/question/65424921/answer/2443700936">如何理解反向传播? - 知乎</a></h3>'
        '<div class="res-rich"><span class="res-list-summary"><em>反向传播用于有效计算梯度</em></span></div></li></ul>'
    )
    hits = parse_so360_html(page)
    assert [h.url for h in hits] == ["https://www.zhihu.com/question/501077471/answer/2402307191", "https://www.zhihu.com/question/65424921/answer/2443700936"]
    assert hits[0].title == "吴恩达深度学习直观理解反向传播"
    assert hits[0].snippet.startswith("本文主要讲述反向传播")
    assert hits[1].snippet == "反向传播用于有效计算梯度"
