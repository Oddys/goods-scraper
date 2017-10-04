# -*- coding: utf-8 -*-
import scrapy
import re
from scrapy_splash import SplashRequest


class JdqnapSpider(scrapy.Spider):
    name = 'jdqnap'
    allowed_domains = ['jd.com']
    start_urls = ['https://search.jd.com/Search?keyword=qnap/']

    # Lua script for handling lazy loading and 'clicking' next button.
    script = """
    function main(splash)              
        local num_scrolls = 10
        local scroll_delay = 1.0

        local scroll_to = splash:jsfunc("window.scrollTo")
        local get_body_height = splash:jsfunc(
            "function() {return document.body.scrollHeight;}"
        )
        
        assert(splash:go(splash.args.url))
        splash:wait(5)
               
        local start = splash.args.start
        if start == 0 then
           splash:runjs("document.getElementsByClassName('fp-next')[0].click();") 
           splash:wait(5)
        end

        for _ = 1, num_scrolls do
            scroll_to(0, get_body_height())
            splash:wait(scroll_delay)
        end
               
        return {
            url = splash:url(),
            html = splash:html(),
        }
    end
    """

    def start_requests(self):
        for url in self.start_urls:
            yield SplashRequest(url, callback=self.parse,
                                endpoint='execute',
                                args={'lua_source': self.script, 'start': 1})

    def parse(self, response):
        items = response.xpath('//li[contains(@class, "gl-item")]')
        for item in items:
            relative_url = item.xpath(
                './/div[contains(@class, "p-name")]/a/@href').extract_first()
            url = response.urljoin(relative_url)
            yield SplashRequest(url, callback=self.parse_item, meta={'URL': url})

        if response.xpath('//a[@class="fp-next"]'):
            yield SplashRequest(response.url, callback=self.parse,
                                endpoint='execute',
                                args={'lua_source': self.script, 'start': 0})

    def parse_item(self, response):
        url = response.meta.get('URL')

        brand = response.xpath(
            '//ul[@id="parameter-brand"]/li/@title').extract_first()

        mpn_with_title = response.xpath(
            '//ul[@class="parameter2 p-parameter-list"]/li[2]/text()').extract_first()
        mpn = re.findall('\D+(\d+)', mpn_with_title)[0]

        name = response.xpath('//div[@class="sku-name"]/text()').extract()[-1].strip()

        price_patterns = ('//span[@class="p-price"]/span/text()',
                          '//span[@class="p-price ys-price"]/span/text()')
        currency_and_number_separately = response.xpath(
            f'{price_patterns[0]} | {price_patterns[1]}').extract()
        price = ''.join(currency_and_number_separately)

        stock_values = {'有货': 1, '无货': 0}
        stock_str = response.xpath(
            '//div[@id="store-prompt"]/strong/text()').extract_first()
        stock = stock_values[stock_str]

        yield {'Brand': brand, 'MPN': mpn, 'URL': url,
               'Name': name, 'Price': price, 'Stock': stock}
