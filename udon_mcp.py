import os
import sys
import time
import json
from typing import List, Optional, Dict, Any

from firecrawl import FirecrawlApp
from firecrawl.firecrawl import ScrapeOptions
from mcp.server.fastmcp import FastMCP

APP_NAME = "firecrawl-udonsharp-mcp"
app = FastMCP(APP_NAME)

FIRECRAWL_API_URL = os.environ.get("FIRECRAWL_API_URL", "http://あなたのアドレス")
FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY", "あなたのトークン（fc-から始まる）")

# 複数のVRChatドメインをサポート
SUPPORTED_DOMAINS = [
    "https://udonsharp.docs.vrchat.com",
    "https://creators.vrchat.com",
    "https://docs.vrchat.com"
]
DOC_DOMAIN = "https://udonsharp.docs.vrchat.com"  # デフォルトドメイン

def _get_firecrawl_app():
    """Get FirecrawlApp instance with custom API URL and key"""
    if not FIRECRAWL_API_KEY:
        print("FIRECRAWL_API_KEY is required", file=sys.stderr)
        sys.exit(1)
    return FirecrawlApp(api_key=FIRECRAWL_API_KEY, api_url=FIRECRAWL_API_URL)

def _ensure_vrchat_url(url_or_path: str, base_domain: str = None) -> str:
    """URL検証を複数のVRChatドメインに対応"""
    if url_or_path.startswith("http://") or url_or_path.startswith("https://"):
        url = url_or_path
        # サポートされているドメインかチェック
        if not any(url.startswith(domain) for domain in SUPPORTED_DOMAINS):
            raise ValueError(f"URL must start with one of: {', '.join(SUPPORTED_DOMAINS)}")
        return url
    else:
        # treat as path under specified domain or default domain
        domain = base_domain or DOC_DOMAIN
        url = f"{domain}{url_or_path if url_or_path.startswith('/') else '/' + url_or_path}"
        return url

@app.tool()
def udonsharp_scrape_page(
    path: Optional[str] = None,
    url: Optional[str] = None,
    formats: Optional[List[str]] = None,
    only_main_content: bool = True,
    base_domain: Optional[str] = None,
) -> Any:
    """
FireCrawl の /scrape を使って、UdonSharp のドキュメントページを 1 ページスクレイピングします。
  - path: 例: '/getting-started/'
  - url: サポートされている VRChat ドメインの完全な URL (指定されている場合、'path' は無視されます)
  - formats: FireCrawl ScrapeOptions.formats (例: ['markdown','html'])
  - only_main_content: ScrapeOptions.onlyMainContent
  - base_domain: パス解決に使用する VRChat ドメインを指定します
    """
    target_url = _ensure_vrchat_url(url or path or "/", base_domain)
    
    firecrawl = _get_firecrawl_app()
    
    try:
        # ScrapeOptionsを作成
        scrape_options = ScrapeOptions(
            formats=formats or ["markdown"],
            onlyMainContent=only_main_content
        )
        
        result = firecrawl.scrape_url(
            target_url,
            scrape_options=scrape_options
        )
        return result
    except Exception as e:
        raise RuntimeError(f"Scrape failed: {str(e)}")

@app.tool()
def udonsharp_crawl_site(
    start_path: str = "/",
    include_paths: Optional[List[str]] = None,
    exclude_paths: Optional[List[str]] = None,
    max_depth: int = 3,
    limit: int = 50,
    ignore_sitemap: bool = False,
    delay: Optional[float] = None,
    formats: Optional[List[str]] = None,
    only_main_content: bool = True,
    wait: bool = True,
    poll_interval_sec: float = 2.0,
    max_wait_sec: int = 300,
) -> Any:
    """
FireCrawl の /crawl を使って UdonSharp のドキュメントをクロールし、オプションで結果を待機します。
  - start_path: ドキュメントドメインの開始パス（デフォルトは '/'）
  - include_paths/exclude_paths: URL パス名の正規表現パターン（ベースドメインからの相対パス）
  - max_depth: 最大深度
  - limit: 最大ページ数
  - ignore_sitemap: サイトマップを無視
  - delay: スクレイピング間隔（秒）
  - formats: ScrapeOptions.formats
  - only_main_content: ScrapeOptions.onlyMainContent
  - wait: true の場合、完了またはタイムアウトまで /crawl/{id} をポーリングします
    """
    start_url = _ensure_vrchat_url(start_path)
    
    firecrawl = _get_firecrawl_app()
    
    try:
        # ScrapeOptionsを作成
        scrape_options = ScrapeOptions(
            formats=formats or ["markdown"],
            onlyMainContent=only_main_content
        )
        
        if wait:
            # Use async crawl with polling
            result = firecrawl.crawl_url(
                start_url,
                include_paths=include_paths or [],
                exclude_paths=exclude_paths or [],
                max_depth=max_depth,
                limit=limit,
                ignore_sitemap=ignore_sitemap,
                scrape_options=scrape_options,
                poll_interval=poll_interval_sec
            )
            return result
        else:
            # Start crawl without waiting
            result = firecrawl.async_crawl_url(
                start_url,
                include_paths=include_paths or [],
                exclude_paths=exclude_paths or [],
                max_depth=max_depth,
                limit=limit,
                ignore_sitemap=ignore_sitemap,
                scrape_options=scrape_options
            )
            return result
    except Exception as e:
        raise RuntimeError(f"Crawl failed: {str(e)}")

@app.tool()
def udonsharp_extract_data(
    paths: Optional[List[str]] = None,
    urls: Optional[List[str]] = None,
    schema: Optional[Dict[str, Any]] = None,
    prompt: Optional[str] = None,
    show_sources: bool = False,
    ignore_sitemap: bool = False,
    include_subdomains: bool = True,
    formats: Optional[List[str]] = None,
    only_main_content: bool = True,
) -> Any:
    """
FireCrawl の /extract を使用して、1 つ以上の UdonSharp ドキュメントページに対して LLM ベースの抽出を実行します。
- パス/URL: 対象ページ（docs ドメイン内にある必要があります）
- スキーマまたはプロンプト: ガイドの抽出（JSON スキーマまたはプロンプト）
- show_sources: 出力にソースを含める
    """
    targets: List[str] = []
    for u in (urls or []):
        targets.append(_ensure_vrchat_url(u))
    for p in (paths or []):
        targets.append(_ensure_vrchat_url(p))
    if not targets:
        raise ValueError("Provide at least one url or path")

    firecrawl = _get_firecrawl_app()
    
    try:
        # Use the correct extract method with URLs list
        result = firecrawl.extract(
            urls=targets,
            prompt=prompt,
            schema=schema
        )
        if show_sources:
            result["sources"] = targets
        return result
    except Exception as e:
        raise RuntimeError(f"Extract failed: {str(e)}")

@app.tool()
def vrchat_json_docs(
    path: Optional[str] = None,
    formats: Optional[List[str]] = None,
    only_main_content: bool = True,
) -> Any:
    """
    VRChatのVRCJSON（データコンテナ）ドキュメントを取得
    - path: 省略時は '/worlds/udon/data-containers/vrcjson' を取得
    """
    target_path = path or "/worlds/udon/data-containers/vrcjson"
    target_url = _ensure_vrchat_url(target_path, "https://creators.vrchat.com")
    
    firecrawl = _get_firecrawl_app()
    
    try:
        # ScrapeOptionsを作成
        scrape_options = ScrapeOptions(
            formats=formats or ["markdown"],
            onlyMainContent=only_main_content
        )
        
        result = firecrawl.scrape_url(
            target_url,
            scrape_options=scrape_options
        )
        return result
    except Exception as e:
        raise RuntimeError(f"VRChat JSON docs scrape failed: {str(e)}")

if __name__ == "__main__":
    # Run MCP over stdio
    app.run()
