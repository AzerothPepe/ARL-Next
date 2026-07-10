import os
import re
import time
import json
import tempfile
from app import utils
from app.config import Config
logger = utils.get_logger()

class SiteScreenshot:
    def __init__(self, sites, concurrency=3, capture_dir="./"):
        self.targets = sites
        self.concurrency = concurrency
        self.capture_dir = capture_dir
        self.screenshot_map = {}
        os.makedirs(self.capture_dir, 0o777, True)

    def gen_filename(self, site):
        filename = site.replace('://', '_')
        return re.sub(r'[^\w\-_\. ]', '_', filename)

    def run(self):
        t1 = time.time()
        logger.info("start screen shot batch, total: {}".format(len(self.targets)))
        if not self.targets:
            return

        tasks = []
        for site in self.targets:
            file_name = '{}/{}.jpg'.format(self.capture_dir, self.gen_filename(site))
            self.screenshot_map[site] = file_name
            tasks.append({
                "url": site,
                "save_name": file_name
            })
            
        # [防卫性补丁 3]：显式指定强编码 utf-8，防止精简系统下 UnicodeEncodeError
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', delete=False, suffix='.json') as f:
            json.dump({"concurrency": self.concurrency, "tasks": tasks}, f)
            tmp_path = f.name
            
        batch_timeout = int(len(self.targets) / self.concurrency * 20 + 60)
        cmd_parameters = ['node', '/code/backend/app/tools/screenshot_pptr.js', '--file={}'.format(tmp_path)]
        logger.debug("screenshot batch {}".format(" ".join(cmd_parameters)))

        try:
            utils.exec_system(cmd_parameters, timeout=batch_timeout)
        except Exception as e:
            logger.error("screenshot batch error: {}".format(e))
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        elapse = time.time() - t1
        logger.info("end screen shot batch elapse {:.2f}s".format(elapse))

def site_screenshot(sites, concurrency=3, capture_dir="./"):
    s = SiteScreenshot(sites, concurrency=concurrency, capture_dir=capture_dir)
    s.run()