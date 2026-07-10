const puppeteer = require('puppeteer-core');
const fs = require('fs');

process.on('unhandledRejection', (reason, promise) => {
    // 仅打印日志，不让进程 crash
});
process.on('uncaughtException', (err) => {
    // 仅打印日志，不让进程 crash
});

async function processUrl(browser, url, save_name) {
    let context;
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
        console.error(`[Security Block] Invalid protocol for URL: ${url}`);
        return;
    }
    try {
        context = await browser.createIncognitoBrowserContext();
        const page = await context.newPage();
        
        page.on('dialog', async dialog => {
            await dialog.dismiss().catch(() => {});
        });

        await page.setRequestInterception(true);
        page.on('request', (req) => {
            if (req.isInterceptResolutionHandled && req.isInterceptResolutionHandled()) return;
            const rt = req.resourceType();
            if (['media', 'font', 'websocket', 'manifest'].includes(rt)) {
                req.abort().catch(() => {});
            } else {
                req.continue().catch(() => {});
            }
        });

        await page.setViewport({ width: 1024, height: 768 });

        // [修复 1]：真实竞技场：保留原生异常，只外挂空钩子吸收游离的 Rejection
        const gotoPromise = page.goto(url, { waitUntil: 'networkidle2', timeout: 8000 });
        gotoPromise.catch(() => {});
        
        let gotoTimeoutId;
        const timeoutPromise = new Promise((_, reject) => {
            gotoTimeoutId = setTimeout(() => reject(new Error('Goto Hard Timeout')), 8000);
        });
        
        try {
            await Promise.race([gotoPromise, timeoutPromise]);
        } catch (gotoErr) {
            console.error(`Goto warning [${url}]:`, gotoErr.message);
        } finally {
            clearTimeout(gotoTimeoutId);
        }
        
        await new Promise(r => setTimeout(r, 1000));

        let height = 768;
        try {
            // [修复 2]：O(1) 复杂度的高度获取，避免 OOM 崩溃
            const evalPromise = page.evaluate(() => {
                if (document.body) { document.body.style.backgroundColor = 'white'; }
                try {
                    let style = document.createElement('style');
                    style.innerHTML = 'html, body { height: auto !important; overflow: visible !important; min-height: 100% !important; }';
                    document.head.appendChild(style);
                } catch(e) {}
                
                let maxH = 768;
                try {
                    maxH = Math.max(
                        document.body ? document.body.scrollHeight : 768,
                        document.documentElement ? document.documentElement.scrollHeight : 768,
                        document.body ? document.body.offsetHeight : 768,
                        document.documentElement ? document.documentElement.offsetHeight : 768,
                        document.body ? document.body.clientHeight : 768,
                        document.documentElement ? document.documentElement.clientHeight : 768
                    );
                } catch(e) {}
                
                return maxH > 2048 ? 2048 : (maxH < 768 ? 768 : maxH);
            });
            evalPromise.catch(() => {}); 
            
            let evalTimeoutId;
            const evalTimeout = new Promise((_, reject) => {
                evalTimeoutId = setTimeout(() => reject(new Error('Evaluate Timeout')), 5000);
            });
            
            height = await Promise.race([evalPromise, evalTimeout]);
            if (typeof height !== 'number') height = 768;
            clearTimeout(evalTimeoutId); 
        } catch (evalErr) {
            console.error(`Evaluate warning [${url}]:`, evalErr.message);
        }

        await page.setViewport({ width: 1024, height: height });
        await page.screenshot({ path: save_name, type: 'jpeg', quality: 30 });

    } catch (e) {
        console.error(`Screenshot error [${url}]:`, e.message);
    } finally {
        if (context) {
            await context.close().catch(() => {});
        }
    }
}

async function main() {
    let url = '';
    let save_name = '';
    let file_path = '';

    for (let i = 0; i < process.argv.length; i++) {
        if (process.argv[i].startsWith('-u=')) {
            url = process.argv[i].substring(3);
        } else if (process.argv[i].startsWith('-s=')) {
            save_name = process.argv[i].substring(3);
        } else if (process.argv[i].startsWith('--file=')) {
            file_path = process.argv[i].substring(7);
        }
    }

    if (!file_path && (!url || !save_name)) {
        process.exit(1);
    }

    let tasks = [];
    let concurrency = 3;

    if (file_path) {
        try {
            const data = JSON.parse(fs.readFileSync(file_path, 'utf8'));
            tasks = data.tasks || [];
            concurrency = data.concurrency || 3;
        } catch (e) {
            process.exit(1);
        }
    } else {
        tasks = [{ url, save_name }];
        concurrency = 1;
    }

    if (tasks.length === 0) {
        process.exit(0);
    }

    const globalTimeout = Math.ceil(tasks.length / concurrency) * 20000 + 30000;
    const timer = setTimeout(() => {
        process.exit(1);
    }, globalTimeout);
    timer.unref();

    let browser;
    
    const cleanupAndExit = async () => {
        if (browser) {
            await browser.close().catch(() => {});
        }
        process.exit(0);
    };
    process.on('SIGTERM', cleanupAndExit);
    process.on('SIGINT', cleanupAndExit);

    try {
        browser = await puppeteer.launch({
            executablePath: '/usr/bin/chromium',
            args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--ignore-certificate-errors'],
            ignoreHTTPSErrors: true
        });

        let index = 0;
        const workers = Array(concurrency).fill(null).map(async () => {
            while (index < tasks.length) {
                const task = tasks[index++];
                await processUrl(browser, task.url, task.save_name);
            }
        });
        
        // [修复 3]：使用 Promise.allSettled 代替 Promise.all，保证无短板完全执行
        await Promise.allSettled(workers);

    } catch (e) {
        console.error("Browser launch error:", e.message);
    } finally {
        if (browser) {
            await browser.close().catch(() => {});
        }
    }
}

main();
