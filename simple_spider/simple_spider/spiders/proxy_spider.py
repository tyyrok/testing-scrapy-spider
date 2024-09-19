import base64
from typing import Any, Iterable

import scrapy
from scrapy.http import Response, Request

URL_FOR_SCRAPING = "http://free-proxy.cz/en/"
LIMIT_PAGES_TO_PARSE = 5


class ProxySpider(scrapy.Spider):
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
        self.pages_parsed = 0

    def start_requests(self) -> Iterable[Request]:
        if self.proxies:
            proxy = self.proxies.pop()
            yield scrapy.Request(
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
                yield {
                    "ip": ip,
                    "port": port
                }
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
