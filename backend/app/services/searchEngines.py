import re
from pyquery import PyQuery as pq
import time
from urllib.parse import quote, urljoin, urlparse
from app import utils

logger = utils.get_logger()


class SoSearch(object):
    def __init__(self, keyword=None, page_num=6):
        self.search_url = "https://www.so.com/s?q={keyword}&pn={page}"
        self.keyword = keyword
        self.page_num = page_num
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        from app.config import Config
        cookie = Config.SO_SEARCH_COOKIE
        if cookie:
            self.headers["Cookie"] = cookie
        self.default_interval = 3.0

    def match_urls(self, html):
        dom = pq(html)
        links = dom("h3.res-title a").items()
        
        urls = set()
        for link in links:
            href = link.attr("data-url") or link.attr("href")
            if not href or not href.startswith("http"):
                continue
            
            try:
                if not re.match(r'^https?:/{2}\w.+$', href):
                    logger.info("url {} is invalid".format(href))
                    continue
                
                resp = utils.http_req(href, "get", headers=self.headers, timeout=(5.1, 5.1))
                match = re.search(r'URL=[\'"]?([^\'">]+)[\'"]?', resp.text, re.I)
                if not match:
                    match = re.search(r'window\.location\.replace\([\'"]([^\'"]+)[\'"]\)', resp.text)
                
                if match:
                    real_url = match.group(1)
                    urls.add(real_url)
            except Exception as e:
                logger.debug("SoSearch URL GET request failed {}: {}".format(href, e))
        return list(urls)

    def run(self):
        urls = []
        # SO pagination is pn=1, 2, 3...
        for page in range(1, self.page_num + 1):
            try:
                if page > 1:
                    time.sleep(self.default_interval)
                url = self.search_url.format(page=page, keyword=quote(self.keyword))
                resp = utils.http_req(url, headers=self.headers)
                
                if resp.status_code != 200:
                    logger.warning("360 search page {} failed with status {}".format(page, resp.status_code))
                    break
                    
                _urls = self.match_urls(resp.text)
                logger.info("360 search url {}, result {}".format(url, len(_urls)))
                if not _urls: 
                    # 遇到无结果说明被限制或者到达末尾
                    break
                urls.extend(_urls)
            except Exception as e:
                logger.warning("360 search page {} failed: {}".format(page, e))
                break 
                
        return urls


class BingSearch(object):
    def __init__(self, keyword=None, page_num=6):
        self.search_url = "https://cn.bing.com/search?q={keyword}&qs=n&form=QBRE&sp=-1&first={page}"
        self.num_pattern = re.compile(r'<span class="sb_count">([^<]+)</span>')
        self.pq_query = "#b_results > li h2 > a"
        self.keyword = keyword
        self.page_num = page_num
        self.headers = {"Accept-Language": "zh-cn"}
        from app.config import Config
        cookie = Config.BING_SEARCH_COOKIE
        if cookie:
            self.headers["Cookie"] = cookie
        self.default_interval = 3
        self.search_result_num = 0
        self.first_html = ""

    def result_num(self):
        url = self.search_url.format(page=1, keyword=quote(self.keyword))
        html = utils.http_req(url, headers=self.headers).text
        self.first_html = html
        result = re.findall(self.num_pattern, html)

        if result:
            # 第一种情况
            result_num = re.findall(r"共 ([\d,]*) 条", result[0])
            if result_num:
                num = int("".join(result_num[0].split(",")))
                self.search_result_num = num

            # 第二种情况
            else:
                result_num_2 = re.findall(r" ([\d,]*) 个结果", result[0])
                if result_num_2:
                    num = int("".join(result_num_2[0].split(",")))
                    self.search_result_num = num
        else:
            logger.warning("Unable to get bing search results， {}".format(self.keyword))
            return 0

        return self.search_result_num

    def match_urls(self, html):
        if "搜索</title>" not in html:
            raise Exception("获取Bing结果异常")

        dom = pq(html)
        result_items = dom(self.pq_query).items()
        urls_result = [item.attr("href") for item in result_items]
        urls = set()
        for u in urls_result:
            urls.add(u)
        return list(urls)

    def run(self):
        self.result_num()
        logger.info("bing search {} results found for keyword {}".format(self.search_result_num, self.keyword))
        urls = []

        # 没有找到直接return
        if self.search_result_num == 0:
            return urls

        for page in range(1, min(int(self.search_result_num / 10) + 2, self.page_num + 1)):
            if page == 1:
                _urls = self.match_urls(self.first_html)
                urls.extend(_urls)
                logger.info("bing search first url result {}".format(len(_urls)))
            else:
                time.sleep(self.default_interval)
                url = self.search_url.format(page=(page - 1) * 10, keyword=quote(self.keyword))
                html = utils.http_req(url, headers=self.headers).text
                _urls = self.match_urls(html)
                logger.info("bing search url {}, result {}".format(url, len(_urls)))
                urls.extend(_urls)
        return urls


def so_search(domain, page_num=6):
    keyword = "site:{}".format(domain)
    b = SoSearch(keyword, page_num)
    urls = b.run()
    urls = [u for u in urls if domain in urlparse(u).netloc]
    return utils.rm_similar_url(urls)


def bing_search(domain, page_num=5):
    urls = []
    keyword = "site:{}".format(domain)
    b = BingSearch(keyword, page_num)
    urls.extend(b.run())
    if b.search_result_num > 1000 and len(urls) > 25:
        keywords = ["admin", "管理|后台", "登陆|密码", "login", "manage", "dashboard", "api",
                    "console"]
        for k in keywords:
            keyword = "site:{} {}".format(domain, k)
            try:
                time.sleep(15)
                b = BingSearch(keyword, page_num=1)
                urls.extend(b.run())
            except Exception as e:
                logger.warning(e)
    urls = [u for u in urls if domain in urlparse(u).netloc]
    return utils.rm_similar_url(urls)


class SearchEngines(object):
    # *** 调用搜索引擎查找URL
    def __init__(self, base_domain):
        self.engines = [bing_search, so_search]
        self.base_domain = base_domain

    def run(self):
        urls = []
        for engine in self.engines:
            try:
                urls.extend(engine(self.base_domain))
                urls = utils.rm_similar_url(urls)
            except Exception as e:
                logger.exception(e)

        return urls


def search_engines(base_domain):
    s = SearchEngines(base_domain)
    return s.run()


if __name__ == '__main__':
    for x in so_search("qq.com", 6):
        print(x)
