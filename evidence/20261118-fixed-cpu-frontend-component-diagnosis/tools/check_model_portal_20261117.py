"""Exercise the real standalone local HTML in an isolated headless browser."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse, json
from playwright.sync_api import sync_playwright

root=Path('C:/Users/Billy/Desktop/Denzic/Companion')
ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--expected-completed',type=int,default=12);ap.add_argument('--final-results',action='store_true');ap.add_argument('--method-lessons',action='store_true');args=ap.parse_args()
out=args.output
out.mkdir(exist_ok=False)
url=(root/'Companion.html').as_uri()
errors=[]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
        headless=True,args=['--disable-background-networking','--no-first-run','--disable-gpu'])
    results=[]
    for label,width,height in [('desktop',1440,1100),('mobile',390,844)]:
        context=browser.new_context(viewport={'width':width,'height':height},device_scale_factor=1)
        context.route('http://**/*',lambda route:route.abort())
        context.route('https://**/*',lambda route:route.abort())
        page=context.new_page()
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(url+'#models',wait_until='load')
        page.locator('#models:not([hidden]) h1').wait_for()
        assert page.locator('#models h1').bounding_box()['y'] >= page.locator('.topbar').bounding_box()['height']
        text=page.locator('#models').inner_text()
        (out/(label+'-visible-text.txt')).write_text(text,encoding='utf-8')
        page.screenshot(path=str(out/(label+'-models.png')),full_page=True)
        missing=[value for value in ['5.14%','18.18%','售卖标准','709','现在怎么改'] if value not in text]
        assert not missing,(label,missing,errors)
        assert '实际结果' in page.locator('.model-history-table').text_content()
        if label=='mobile':
            assert page.locator('.model-history-table td[data-label="实际结果"]').count()==7
        assert f'{args.expected_completed}/12' in text or f'{args.expected_completed} / 12' in text,text[:1200]
        assert '15.94%' in text and '正式参数更新' in text and '1828' in text
        if args.final_results:
            c=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1')
            score=json.loads((c/'gpu-owned-evening20261117-r2/paired-score.json').read_text())
            card=page.locator('.model-training').inner_text()
            assert '457 / 457' in card and '1828 / 1828' in card
            assert f'{score["candidateWer"]*100:.2f}%' in card and str(score['candidateErrors']) in card
            assert '完整会议验证仍待完成' in card if score['advanceToCompleteSources'] else '未通过中间筛选' in card
            cpu=json.loads((c/'english-accuracy-reference-20261117/customer-cpu-probe-r1/score.json').read_text())
            for row in cpu['summaries']:
                assert f'{row["errorRate"]*100:.2f}%' in text and f'RTF {row["realTimeFactor"]:.3f}' in text
            assert '尚非已装产品验收' in text
            page.locator('.model-training').screenshot(path=str(out/(label+'-final-training.png')))
            page.locator('article').filter(has=page.get_by_role('heading',name='无需独显：现有本地模型的CPU实测',exact=True)).screenshot(path=str(out/(label+'-cpu-probe.png')))
        if args.method_lessons:
            report=json.loads((root/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1/week-direction-review-20261117.json').read_text(encoding='utf-8'))
            lessons=report['lessonsForNextExecution20261117']
            assert page.locator('.model-method-step').count()==4
            assert page.locator('.model-lesson').count()==len(lessons)==8
            assert '已落实的新工作方式' in text and '当前工作点' in text
            assert page.evaluate('data.modelProgress.workMethod.state')=='ACTIVE_REFERENCE_TO_CLIENT_DIAGNOSIS_FIRST'
            frontend=page.evaluate('data.modelProgress.workMethod.frontendDiagnosis || null')
            if frontend:
                detail=page.locator('.model-frontend-diagnosis')
                assert frontend['title'] in detail.inner_text() and frontend['validation'] in detail.inner_text()
                assert Path(detail.get_by_role('button',name='复制预处理数值依据',exact=False).get_attribute('data-copy')).is_file()
                if frontend.get('scores'):
                    values=frontend['scores']
                    assert all(f'{entry["wer"]:.2%}' in detail.inner_text() for entry in values.values())
                    assert '结束这份部署配方' in detail.inner_text()
                    assert Path(detail.get_by_role('button',name='复制固定权重对照评分',exact=False).get_attribute('data-copy')).is_file()
            comparison=page.evaluate('data.modelProgress.workMethod.shortComparison || null')
            if comparison:
                detail=page.locator('.model-first-control');detail.locator('summary').click()
                assert '当前CPU导出配方未通过' in detail.inner_text()
                for row in comparison['summaries']:
                    assert f'{row["errors"]} / {row["referenceWords"]}' in detail.inner_text()
                assert '与原研发成绩不构成时间趋势' in detail.inner_text()
                detail.screenshot(path=str(out/(label+'-first-control.png')))
            for lesson in lessons:
                card=page.locator(f'.model-lesson[data-lesson="{lesson["id"]}"]')
                assert lesson['evidence'] in card.inner_text()
                details=card.locator('details')
                if not details.evaluate('(el)=>el.open'):details.locator('summary').click()
                assert lesson['action'] in card.inner_text() and lesson['reopen'] in card.inner_text()
                assert [b.get_attribute('data-copy') for b in card.locator('button[data-copy]').all()]==lesson['sources']
                assert all(Path(s).is_file() for s in lesson['sources'])
            page.locator('.model-work-method').screenshot(path=str(out/(label+'-working-method.png')))
            page.locator('.model-lesson[data-lesson="long-training"]').screenshot(path=str(out/(label+'-training-lesson.png')))
        assert page.locator('nav [data-page]').count()==9
        overflow=page.evaluate('document.documentElement.scrollWidth-window.innerWidth')
        assert overflow<=1,(label,overflow)
        page.screenshot(path=str(out/(label+'-models.png')),full_page=True)
        page.goto(url+'#overview',wait_until='load')
        page.locator('#overview:not([hidden]) .model-overview').wait_for()
        assert '18.18%' in page.locator('.model-overview').inner_text()
        if args.method_lessons:
            assert page.locator('.model-method-announcement').is_visible()
            assert '工作方式已调整并落实' in page.locator('.model-method-announcement').inner_text()
        if label=='desktop':
            page.screenshot(path=str(out/'desktop-overview.png'),full_page=False)
            page.locator('#search').fill('英文')
            page.locator('#search-results a[href="#models"]').click()
            page.locator('#models:not([hidden]) h1').wait_for()
            if args.method_lessons:
                for query in ['教训','工作方式']:
                    page.locator('#search').fill(query)
                    assert page.locator('#search-results a[href="#models"]').is_visible()
                    page.locator('#search-results a[href="#models"]').click()
        results.append({'viewport':label,'width':width,'globalHorizontalOverflowPx':overflow,
                        'modelPageVisible':True,'overviewSummaryVisible':True,'offlineHtml':True})
        context.close()
    browser.close()
assert not errors,errors
receipt={'at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
 'state':'PASS_STANDALONE_MODEL_PAGE_DESKTOP_MOBILE_AND_SEARCH','results':results,
 'javascriptErrors':errors,'externalNetworkAllowed':False,'ordinaryUserBrowserProfileUsed':False,
 'productModelQualityQualified':False,'browser':'Isolated headless Edge via Playwright'}
(out/'result.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt,ensure_ascii=False))
