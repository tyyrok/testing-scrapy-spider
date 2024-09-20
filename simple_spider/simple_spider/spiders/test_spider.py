import json
from datetime import datetime, UTC
from typing import Self

import scrapy
from scrapy import signals
from scrapy.crawler import Crawler
from scrapy.http import Request, Response




class MySpider(scrapy.Spider):
    name = "send"
    start_urls = ["https://test-rg8.ddns.net/task"]

    @classmethod
    def from_crawler(cls, crawler: Crawler, *args, **kwargs) -> Self:
        spider = super(MySpider, cls).from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.spider_closed, signal=signals.spider_closed)
        return spider

    def spider_closed(self, spider, reason):
        start_time = self.crawler.stats.get_value('start_time')
        finish_time = datetime.now(UTC)
        spent_time = str(finish_time - start_time).split(".")[0]
        with open("time.txt", "w") as f:
            f.write(f"{spent_time}\n")

    def parse(self, response: Response):
        # Delay processing to wait for JavaScript updates
        yield Request(
            url="https://test-rg8.ddns.net/api/get_token",  # URL where you need to submit data
            method='GET',
            callback=self.post_request
        )


    def post_request(self, response):
        response_cookie = response.headers.get('Set-Cookie')
        form_token = response_cookie.decode("utf-8").split(";")[0]
        cookies = {
            "form_token": form_token.split("=")[1],
            "x-user_id": "t_7e7ea5ef"
        }
        print("FUCK ", cookies)
        data = {"user_id": "t_7e7ea5ef", "len": 3, "proxies": "129.213.89.36:80, 129.213.89.36:80, 129.213.89.36:80"}
        yield Request(
            url="https://test-rg8.ddns.net/api/post_proxies",  # URL where you need to submit data
            method='POST',
            body=json.dumps(data),
            cookies=cookies,
            headers={'Content-Type': 'application/json'},
            callback=self.after_submission,
            cb_kwargs=dict(proxy_chunk=[data["proxies"]])
        )
        

    def after_submission(self, response: Response, proxy_chunk: list):
        save_id = response.json()["save_id"]
        yield {
            save_id: proxy_chunk
        }