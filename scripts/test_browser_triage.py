import asyncio
import json
import os
import subprocess
import sys
import time
import aiohttp
import base64

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
USER_DATA_DIR = r"C:\Users\Likitha\.gemini\antigravity\scratch\chrome_temp_profile"

async def run_cdp_test():
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    
    # Launch Chrome headless with remote debugging
    cmd = [
        CHROME_PATH,
        "--headless=new",
        "--remote-debugging-port=9222",
        f"--user-data-dir={USER_DATA_DIR}",
        "--window-size=1440,900",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "about:blank"
    ]
    proc = subprocess.Popen(cmd)
    print(f"Launched Chrome (PID: {proc.pid})")
    
    try:
        await asyncio.sleep(2.0)
        
        async with aiohttp.ClientSession() as session:
            # Get list of targets from CDP
            targets_url = "http://127.0.0.1:9222/json"
            async with session.get(targets_url) as resp:
                targets = await resp.json()
            
            page_target = next(t for t in targets if t.get("type") == "page")
            ws_url = page_target["webSocketDebuggerUrl"]
            print(f"Connecting to CDP WebSocket: {ws_url}")
            
            async with session.ws_connect(ws_url) as ws:
                msg_id = 0
                async def send_command(method, params=None):
                    nonlocal msg_id
                    msg_id += 1
                    payload = {"id": msg_id, "method": method, "params": params or {}}
                    await ws.send_json(payload)
                    while True:
                        msg = await ws.receive_json()
                        if msg.get("id") == payload["id"]:
                            return msg.get("result", {})

                # Enable Page, Runtime, Network domains
                await send_command("Page.enable")
                await send_command("Runtime.enable")
                await send_command("Network.enable")
                
                print("Navigating to http://127.0.0.1:8000...")
                await send_command("Page.navigate", {"url": "http://127.0.0.1:8000"})
                await asyncio.sleep(3.0)

                async def eval_js(expr):
                    res = await send_command("Runtime.evaluate", {"expression": expr, "returnByValue": True})
                    return res.get("result", {}).get("value")

                async def take_screenshot(filename):
                    res = await send_command("Page.captureScreenshot", {"format": "png"})
                    data = base64.b64decode(res["data"])
                    filepath = os.path.join(os.getcwd(), filename)
                    with open(filepath, "wb") as f:
                        f.write(data)
                    print(f"[Screenshot Saved]: {filepath} ({len(data)} bytes)")
                    return filepath

                # Step 1: Initial Page State Verification
                title = await eval_js("document.title")
                banner_text = await eval_js("document.querySelector('header')?.innerText || ''")
                print(f"Initial Page Title: {title}")
                print(f"Header Banner Text:\n{banner_text.strip()}\n")

                # Step 2: Test Stage 5 Selection & INC-1005 Triage
                print("\n" + "=" * 60)
                print("TESTING: Stage 5 Selection -> INC-1005 Triage")
                print("=" * 60)
                
                # Click the Stage 5 button
                click_stage5 = await eval_js("""
                    (() => {
                        const buttons = Array.from(document.querySelectorAll('button'));
                        const btn = buttons.find(b => b.innerText.includes('5: Deploy OOM'));
                        if (btn) {
                            btn.click();
                            return 'Clicked Stage 5 button';
                        }
                        return 'Stage 5 button not found';
                    })()
                """)
                print("Stage 5 Click Result:", click_stage5)
                await asyncio.sleep(2.0)

                # Click INC-1005 in the feed
                click_inc1005 = await eval_js("""
                    (() => {
                        const divs = Array.from(document.querySelectorAll('div'));
                        const card = divs.find(d => d.innerText && d.innerText.includes('INC-1005') && d.innerText.includes('P1-CRITICAL'));
                        if (card) {
                            card.click();
                            return 'Clicked INC-1005 feed card';
                        }
                        return 'INC-1005 card not found';
                    })()
                """)
                print("INC-1005 Click Result:", click_inc1005)
                await asyncio.sleep(2.0)

                # Extract and verify Stage 5 results
                confidence_text = await eval_js("""
                    (() => {
                        const el = Array.from(document.querySelectorAll('*')).find(e => e.innerText && e.innerText.includes('CONFIDENCE') && !e.children.length);
                        return el ? el.innerText : 'Not found';
                    })()
                """)
                hypothesis_text = await eval_js("""
                    (() => {
                        const el = document.querySelector('.leading-snug.text-gray-100') || Array.from(document.querySelectorAll('div')).find(d => d.innerText && d.innerText.includes('Payment-service OOMKilled caused by commit'));
                        return el ? el.innerText : 'Not found';
                    })()
                """)
                recall_badge_count = await eval_js("""
                    (() => {
                        const badges = Array.from(document.querySelectorAll('span'));
                        const badge = badges.find(b => b.innerText === '3');
                        return badge ? badge.innerText : 'Not found';
                    })()
                """)
                recalled_elements = await eval_js("""
                    (() => {
                        const text = document.body.innerText;
                        const has1010 = text.includes('INC-1010');
                        const has1016 = text.includes('INC-1016');
                        const has1002 = text.includes('INC-1002');
                        return { has1010, has1016, has1002 };
                    })()
                """)

                print("\n[VERIFICATION RESULTS FOR STAGE 5 / INC-1005]:")
                print(f"  Confidence Rating : {confidence_text}")
                print(f"  Hypothesis Text   : {hypothesis_text}")
                print(f"  Recall Count Badge: {recall_badge_count}")
                print(f"  Recalled Precedents Found: {recalled_elements}")
                
                await take_screenshot("screenshot_stage5_inc1005.png")

                # Step 3: Test Stage 12 Selection & INC-1012 Triage
                print("\n" + "=" * 60)
                print("TESTING: Stage 12 Selection -> INC-1012 Triage")
                print("=" * 60)
                click_stage12 = await eval_js("""
                    (() => {
                        const buttons = Array.from(document.querySelectorAll('button'));
                        const btn = buttons.find(b => b.innerText.includes('12: Disambiguate'));
                        if (btn) { btn.click(); return 'Clicked Stage 12 button'; }
                        return 'Stage 12 button not found';
                    })()
                """)
                print("Stage 12 Click Result:", click_stage12)
                await asyncio.sleep(2.0)

                click_inc1012 = await eval_js("""
                    (() => {
                        const divs = Array.from(document.querySelectorAll('div'));
                        const card = divs.find(d => d.innerText && d.innerText.includes('INC-1012'));
                        if (card) { card.click(); return 'Clicked INC-1012 feed card'; }
                        return 'INC-1012 card not found';
                    })()
                """)
                print("INC-1012 Click Result:", click_inc1012)
                await asyncio.sleep(2.0)

                conf12 = await eval_js("""
                    (() => {
                        const el = Array.from(document.querySelectorAll('*')).find(e => e.innerText && e.innerText.includes('CONFIDENCE') && !e.children.length);
                        return el ? el.innerText : 'Not found';
                    })()
                """)
                hyp12 = await eval_js("""
                    (() => {
                        const text = document.body.innerText;
                        return text.includes('Organic traffic surge') ? 'Organic traffic surge hypothesis present' : 'Not found';
                    })()
                """)
                rec12 = await eval_js("""
                    (() => {
                        const text = document.body.innerText;
                        return { has1007: text.includes('INC-1007') };
                    })()
                """)
                print(f"  Stage 12 Confidence: {conf12}")
                print(f"  Stage 12 Hypothesis: {hyp12}")
                print(f"  Stage 12 Precedents: {rec12}")
                await take_screenshot("screenshot_stage12_inc1012.png")

                # Step 4: Test Stage 20 Selection & INC-1020 Triage
                print("\n" + "=" * 60)
                print("TESTING: Stage 20 Selection -> INC-1020 Triage")
                print("=" * 60)
                click_stage20 = await eval_js("""
                    (() => {
                        const buttons = Array.from(document.querySelectorAll('button'));
                        const btn = buttons.find(b => b.innerText.includes('20: Obsolete Fix'));
                        if (btn) { btn.click(); return 'Clicked Stage 20 button'; }
                        return 'Stage 20 button not found';
                    })()
                """)
                print("Stage 20 Click Result:", click_stage20)
                await asyncio.sleep(2.0)

                click_inc1020 = await eval_js("""
                    (() => {
                        const divs = Array.from(document.querySelectorAll('div'));
                        const card = divs.find(d => d.innerText && d.innerText.includes('INC-1020'));
                        if (card) { card.click(); return 'Clicked INC-1020 feed card'; }
                        return 'INC-1020 card not found';
                    })()
                """)
                print("INC-1020 Click Result:", click_inc1020)
                await asyncio.sleep(2.0)

                conf20 = await eval_js("""
                    (() => {
                        const el = Array.from(document.querySelectorAll('*')).find(e => e.innerText && e.innerText.includes('CONFIDENCE') && !e.children.length);
                        return el ? el.innerText : 'Not found';
                    })()
                """)
                hyp20 = await eval_js("""
                    (() => {
                        const text = document.body.innerText;
                        return text.includes('PAYMENT_BATCH_SIZE to 5000 on Java 21') ? 'Java 21 batch OOM hypothesis present' : 'Not found';
                    })()
                """)
                rec20 = await eval_js("""
                    (() => {
                        const text = document.body.innerText;
                        return {
                            has1016: text.includes('INC-1016'),
                            hasObsoleteWarning: text.includes('OBSOLETE') || text.includes('ZGC')
                        };
                    })()
                """)
                print(f"  Stage 20 Confidence: {conf20}")
                print(f"  Stage 20 Hypothesis: {hyp20}")
                print(f"  Stage 20 Precedents: {rec20}")
                await take_screenshot("screenshot_stage20_inc1020.png")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()
        print("Chrome process terminated.")

if __name__ == "__main__":
    asyncio.run(run_cdp_test())
