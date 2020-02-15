import os
import pickle
import re
import time

from pyquery import PyQuery as pq
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
import pymongo
from config import *

#连接数据库
client = pymongo.MongoClient(MONGO_URL)
db = client[MONGO_DB]


# 创建Chrome对象
chrome_options = Options()
chrome_options.add_argument('--headless')
browser = webdriver.Chrome(options=chrome_options)
wait = WebDriverWait(browser, 10)


def get_taobao_cookies():
    url = 'https://www.taobao.com/'
    browser.get('https://login.taobao.com/')
    while True:
        print("please login to Taobao!")
        time.sleep(4)
        while browser.current_url == url:
            tbCookies = browser.get_cookies()
            browser.quit()
            output_path = open('taobaoCookies.pickle', 'wb')
            pickle.dump(tbCookies, output_path)
            output_path.close()
            return tbCookies


def read_taobao_cookies():
    if os.path.exists('taobaoCookies.pickle'):
        read_path = open('taobaoCookies.pickle', 'rb')
        tbCookies = pickle.load(read_path)
    else:
        tbCookies = get_taobao_cookies()
    return tbCookies


def search():
    try:
        # 直接调用get()方法不行了,淘宝有反爬虫机制,所以要先传一个cookies进去
        # browser.get('https://www.taobao.com')
        cookies = read_taobao_cookies()
        # add_cookie之前要先打开一下网页,不然他妈的会报invalid domain错误. 日了狗了
        browser.get('https://www.taobao.com')
        for cookie in cookies:
            # stackoverflow查到的,不知道为啥,要把expiry这个键值对删掉,不然的话,会报invalid argument,MD!
            if 'expiry' in cookie:
                del cookie['expiry']
            browser.add_cookie(cookie)
        browser.get('https://www.taobao.com')
        input_text = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#q')))
        submit = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, '#J_TSearchForm > div.search-button > button')))
        input_text.send_keys('口罩')
        submit.click()
        total = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '#mainsrp-pager > div > div > div > div.total')))
        get_products()
        return total.text
    except TimeoutException:
        # 注意这是个递归,如果超时的话,就再请求一次
        return search()


def next_page(page_number):
    try:
        input_text = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '#mainsrp-pager > div > div > div > div.form > input')))
        submit = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, '#mainsrp-pager > div > div > div > div.form > span.btn.J_Submit')))
        input_text.clear()
        input_text.send_keys(page_number)
        submit.click()
        wait.until(EC.text_to_be_present_in_element(
            (By.CSS_SELECTOR, '#mainsrp-pager > div > div > div > ul > li.item.active > span'), str(page_number)))
        get_products()
    except TimeoutException:
        return next_page(page_number)


def get_products():
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#mainsrp-itemlist .items .item')))
    html = browser.page_source
    doc = pq(html)
    items = doc('#mainsrp-itemlist .items .item').items()
    for item in items:
        product = {
            # 不知道为什么,取src的话,会出现一些s.gif的链接,所以改取原始图片
            'image': item.find('.pic .img').attr('data-src'),
            'price': item.find('.price').text(),
            'deal': item.find('.deal-cnt').text()[:-3],
            'title': item.find('.title').text(),
            'shop': item.find('.shop').text(),
            'location': item.find('.location').text()
        }
        save_to_mongo(product)


def save_to_mongo(result):
    try:
        if db[MONGO_TABLE].insert_one(result):
            print('存储到MONGODB成功:',result)
    except Exception:
        print('存储到MONGODB失败',result)

def main():
    total = search()
    total = int(re.compile('(\d+)').search(total).group(1))
    for i in range(2, total + 1):
        next_page(i)
    browser.close()

if __name__ == '__main__':
    main()
