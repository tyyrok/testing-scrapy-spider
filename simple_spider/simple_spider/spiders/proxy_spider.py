import base64
import json
from datetime import datetime, UTC
from typing import Any, Iterable, Self

from scrapy import signals, Spider
from scrapy.crawler import Crawler
from scrapy.http import Response, Request

URL_FOR_SCRAPING = "http://free-proxy.cz/en/"
URL_FOR_SENDING_DATA = "https://test-rg8.ddns.net/task"
URL_FOR_GETTING_FORM_TOKEN = "https://test-rg8.ddns.net/api/get_token"
URL_FOR_SENDING_RESULT = "https://test-rg8.ddns.net/api/post_proxies"
LIMIT_PAGES_TO_PARSE = 5
LIMIT_VALUES_TO_SEND = 9
TOKEN = "t_7e7ea5ef"


class ProxySpider(Spider):
    name = "proxy"
    parsed_proxies = []
    max_retries = 2

    proxies = [
        "http://188.114.99.171:80",
        "http://188.114.96.46:80",
        "http://185.238.228.96:80",

    ]

    def __init__(self, name: str | None = None, **kwargs: Any):
        super().__init__(name, **kwargs)
        self.pages_parsed = 1

    @classmethod
    def from_crawler(cls, crawler: Crawler, *args, **kwargs) -> Self:
        spider = super(ProxySpider, cls).from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.spider_closed, signal=signals.spider_closed)
        return spider

    def start_requests(self) -> Iterable[Request]:
        if self.proxies:
            proxy = self.proxies.pop()
            yield Request(
                url=URL_FOR_SCRAPING,
                callback=self.parse,
                errback=self.error_handle,
                dont_filter=True,
                meta={
                    "proxy": proxy,
                    'retry_count': 0
                },
            )
        else:
            self.log("No proxies presented!")

    def error_handle(self, failure):
        request: Request = failure.request
        proxy = request.meta.get("proxy")
        retry_count = request.meta.get("retry_count", 0)
        self.log(f"Proxy failed: {proxy} | Retry found: {retry_count}")
        if self.proxies:
            new_proxy = self.proxies.pop()
            self.log(f"Retrying with new proxy {new_proxy}")
            
            retry_request = request.copy()
            retry_request.meta["proxy"] = new_proxy
            retry_request.meta["retry_count"] = retry_count + 1
            yield retry_request
        else:
            self.log(f"All proxies are failed for url {URL_FOR_SCRAPING}")

    def parse(self, response: Response):
        for elem in response.xpath('//*[@id="proxy_list"]/tbody/tr'):       
            script_text = elem.xpath('td[1]/script/text()').get()
            if script_text:
                decoded_ip = script_text.split('"')[1]
                ip = base64.b64decode(decoded_ip).decode("utf-8")
                port = elem.xpath('td[2]/span/text()').get()
                #yield {
                #    "ip": ip,
                #    "port": port
                #}
                self.parsed_proxies.append(f"{ip}:{port}")
        self.pages_parsed += 1
        if self.pages_parsed <= LIMIT_PAGES_TO_PARSE:
            next_page = response.xpath('/html/body/div[2]/div[2]/div[7]/a[last()]')[0]
            yield response.follow(
                next_page,
                callback=self.parse,
                errback=self.error_handle,
                dont_filter=True,
                meta={
                    "proxy": response.meta.get('proxy'),
                    'retry_count': response.meta.get('retry_count', 0)
                },
            )
        else:
            yield Request(
                url=URL_FOR_SENDING_DATA, 
                method='GET',
                callback=self.get_token
            )
    """
    def send_callback(self, reason):
        self.crawler.engine.crawl(
            Request(
                url=URL_FOR_SENDING_DATA, 
                method='GET',
                callback=self.get_token
            )
        )
    """
    def get_token(self, reason):
        yield Request(
            url=URL_FOR_GETTING_FORM_TOKEN,
            callback=self.send_data
        )

    def send_data(self, response: Response):
        response_cookie = response.headers.get('Set-Cookie')
        form_token = response_cookie.decode("utf-8").split(";")[0]
        cookies = {
            "form_token": form_token.split("=")[1],
            "x-user_id": "t_7e7ea5ef"
        }
        proxy_chunks = [
            self.parsed_proxies[i: i + LIMIT_VALUES_TO_SEND]
            for i in range(0, len(self.parsed_proxies), LIMIT_VALUES_TO_SEND)
        ]
        for chunk in proxy_chunks:
            data = self.prepare_data(chunk)
            yield Request(
                url=URL_FOR_SENDING_RESULT,
                method='POST',
                body=json.dumps(data),
                cookies=cookies,
                headers={'Content-Type': 'application/json'},
                callback=self.after_submission,
                cb_kwargs=dict(proxy_chunk=chunk)
            )

    def prepare_data(self, proxies: list[str]) -> dict:
        return {
            "user_id": TOKEN,
            "len": len(proxies),
            "proxies": ", ".join(proxies)
        }

    def after_submission(self, response: Response, proxy_chunk: list):
        save_id = response.json()["save_id"]
        yield {
            save_id: proxy_chunk
        }

    def spider_closed(self, spider, reason):
        start_time = self.crawler.stats.get_value('start_time')
        finish_time = datetime.now(UTC)
        spent_time = str(finish_time - start_time).split(".")[0]
        with open("time.txt", "w") as f:
            f.write(f"{spent_time}\n")
