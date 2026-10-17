#!/usr/bin/env python3
"""Read-only checks of current navigation, full calendar and mobile layout."""
import json
import os
from pathlib import Path


def main():
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait, Select
    origin = 'https://kingdomcircuit.com'
    output = Path('browser-audit'); output.mkdir(exist_ok=True)
    result = {'runId': os.environ.get('GITHUB_RUN_ID'), 'checks': []}
    def check(name, condition, detail=''):
        result['checks'].append({'name':name,'status':'pass' if condition else 'fail','detail':detail})
    for width in (1440,390,320,768):
        driver = None
        try:
            options = webdriver.ChromeOptions()
            for arg in ('--headless=new','--no-sandbox','--disable-dev-shm-usage'): options.add_argument(arg)
            if width < 1000:
                options.add_experimental_option('mobileEmulation', {'deviceMetrics':{'width':width,'height':900,'pixelRatio':1}})
            else: options.add_argument('--window-size=1440,1000')
            driver = webdriver.Chrome(options=options); driver.set_page_load_timeout(45)
            wait = WebDriverWait(driver,30)
            for route in ('/','/shows/','/artists/','/artists/kb/','/about-us/','/shows/this-weekend/'):
                driver.get(origin+route+'?browser-retest='+str(os.environ.get('GITHUB_RUN_ID','local')))
                wait.until(lambda d:d.find_elements(By.TAG_NAME,'h1'))
                metrics=driver.execute_script('return [innerWidth,document.documentElement.scrollWidth,document.body.scrollWidth]')
                check(f'{width}px {route} no overflow',max(metrics[1:])<=metrics[0]+2,str(metrics))
                check(f'{width}px {route} main heading',len(driver.find_elements(By.TAG_NAME,'h1'))==1)
                check(f'{width}px {route} production canonical',driver.find_element(By.CSS_SELECTOR,'link[rel="canonical"]').get_attribute('href')==origin+route)
                if route == '/':
                    nav=driver.find_element(By.CSS_SELECTOR,'nav[aria-label="Primary navigation"]')
                    for path in ('/shows/','/shows/this-weekend/','/shows/this-month/','/festivals/','/new-shows/','/artists/','/about-us/'):
                        links=nav.find_elements(By.CSS_SELECTOR,f'a[href="{path}"]')
                        check(f'{width}px navigation {path}',len(links)==1 and links[0].is_displayed())
                    check(f'{width}px approved discovery home',bool(driver.find_elements(By.CSS_SELECTOR,'[data-national-home]')))
                    sizes=driver.execute_script('return [...document.querySelectorAll("[data-discovery-show]:not([hidden])")].map(n=>[Math.round(n.getBoundingClientRect().width),Math.round(n.getBoundingClientRect().height)])')
                    check(f'{width}px uniform show cards',not sizes or len(set(map(tuple,sizes)))==1,str(sizes[:4]))
                    check(f'{width}px Facebook link',bool(driver.find_elements(By.CSS_SELECTOR,'a[href="https://www.facebook.com/profile.php?id=61593510924754"]')))
                    driver.save_screenshot(str(output/f'{width}px-home.png'))
                if route == '/shows/' and width in (1440,390):
                    wait.until(lambda d:len(d.find_elements(By.CSS_SELECTOR,'[data-state-filter] option'))>1)
                    cards=lambda:driver.find_elements(By.CSS_SELECTOR,'[data-event-card]')
                    visible=lambda:[c for c in cards() if c.is_displayed()]
                    baseline=len(visible())
                    check(f'{width}px full calendar renders',baseline>0,f'{baseline} visible')
                    state=Select(driver.find_element(By.CSS_SELECTOR,'[data-state-filter]'))
                    chosen=next((o for o in state.options if o.get_attribute('value') and any(c.get_attribute('data-state')==o.get_attribute('value') for c in visible())),None)
                    if chosen:
                        value=chosen.get_attribute('value'); state.select_by_value(value)
                        wait.until(lambda d:visible() and all(c.get_attribute('data-state')==value for c in visible()))
                        check(f'{width}px state filter',True)
                    driver.find_element(By.CSS_SELECTOR,'[data-search-filter]').send_keys('kc-no-such-show-947213')
                    wait.until(lambda d:not visible()); check(f'{width}px honest empty search',True)
                    reset=driver.find_element(By.CSS_SELECTOR,'[data-reset-filters]')
                    if not reset.is_displayed():
                        for summary in driver.find_elements(By.CSS_SELECTOR,'[data-event-filters] details:not([open]) > summary'): summary.click()
                    reset.click(); wait.until(lambda d:len(visible())==baseline)
                    check(f'{width}px reset restores current calendar',True)
                    for value,name in (('TX','Texas'),('FL','Florida')):
                        state.select_by_value(value)
                        wait.until(lambda d:d.find_element(By.CSS_SELECTOR,'[data-selected-state]').get_attribute('href')==origin+'/shows/'+name.lower()+'/')
                        check(f'{width}px shortcut follows {name}',name in driver.find_element(By.CSS_SELECTOR,'[data-selected-state]').text)
                if route == '/artists/kb/':
                    rows=driver.find_elements(By.CSS_SELECTOR,'.kc-rd-show-row')
                    details=driver.find_elements(By.CSS_SELECTOR,'[data-artist-show-details] [data-event-card]')
                    check(f'{width}px detailed shows retained below summary',len(rows)==len(details),f'{len(rows)} summary / {len(details)} full cards')
            driver.save_screenshot(str(output/f'{width}px.png'))
        except Exception as exc:
            check(f'{width}px browser sequence',False,f'{type(exc).__name__}: {str(exc)[:1000]}')
            if driver: driver.save_screenshot(str(output/f'{width}px-failure.png'))
        finally:
            if driver: driver.quit()
    result['failed']=sum(c['status']=='fail' for c in result['checks'])
    result['passed']=len(result['checks'])-result['failed']
    result['overall']='fail' if result['failed'] else 'pass'
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps(result,indent=2))
    return bool(result['failed'])


if __name__ == '__main__': raise SystemExit(main())
