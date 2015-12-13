import aiohttp
import asyncio
from asyncio import coroutine
import jinja2
import re
import traceback
from functools import partial

# CDNHOST = 'http://hacfun-tv.n1.yun.tf:8999/Public/Upload'
CDNHOST = 'http://60.190.217.166:8999/Public/Upload'
_conn = aiohttp.TCPConnector(use_dns_cache=True, limit=30, force_close=True)


async def get_data(url, callback=None, as_type='json', conn=_conn):
    try:
        # async with aiohttp.get(url, connector=conn) as r:
        r = await aiohttp.get(url, connector=conn)
        if 1==1:
            data = await getattr(r, as_type)()
            r.close()
    except Exception as e:
        print('exception!..', traceback.format_exc())
        data = ''

    print('finish request', url)
    if callback:
        asyncio.ensure_future(callback(data, url))
    else:
        return data




class ImageManager:
    def __init__(self, loop, max_tasks=100):
        self.url_set  = set()
        self.sem = asyncio.Semaphore(max_tasks)
        self.busying = set()
        self.loop = loop

    async def submit(self, url):
        if url in self.url_set:
            return
        else:
            self.url_set.add(url)
        print('prepare download', url)
        file_name = url.split('/')[-1]
        file_path = 'image/' + file_name
        self.busying.add(url)
        await self.sem.acquire()
        print('enter downloading')
        task = asyncio.ensure_future(get_data(url, as_type='read',
                                              callback=partial(self.save_file, file_path=file_path)))
        task.add_done_callback(lambda t:self.sem.release())
        # task.add_done_callback(lambda t:self.save_file(task=t, file_path=file_path))
        task.add_done_callback(lambda t:self.busying.remove(url))

    async def save_file(self, data, url, file_path):
        content = data
        if not content:
            print('no data available')
            return

        print('save file to ', file_path)


        with open(file_path, 'wb') as f:
            f.write(content)
        print('sace sucess!')

    async def wait_all_task_done(self):
        print('begin waiting')
        while True:
            await asyncio.sleep(1)
            if not self.busying:
                break

        # for t in asyncio.Task.all_tasks():
        #     t.cancel()
        #     print('exit task',t)
        self.loop.stop()

    async def inter_status_info(self, inter=3):
        print('start inter status info function!')
        while self.busying:
            print('this is {} in busying'.format(len(self.busying)))
            urls = [url for i, url in enumerate(self.busying) if i<3]
            print('urls[3] is', urls)
            await asyncio.sleep(inter)


def url_page_combine(base_url, num):
    return base_url + '?page=' + str(num)




class Page:
    def __init__(self, url=None, page_num=1, data=None):
        self._page = page_num
        self.base_url = url
        self.data = data



    @classmethod
    async def from_url(cls, base_url, page_num):
        data = await get_data(url_page_combine(base_url, page_num))
        return cls(base_url, page_num, data)

    def thread_list(self):
        """
        list of blocks
        :return:
        """
        top = Block(self.data['threads'])

        ext = [Block(reply) for reply in self.data['replys']]
        ext.insert(0, top)
        return ext



    @property
    def next_page_num(self):
        if self.has_next():
            return self._page + 1


    @property
    def next_page_info(self):
        page_num = self._page + 1
        return (self.base_url, page_num)

    def has_next(self):
        return self._page < self.data['page']['size']




class Block:
    """ proxy for div
    """
    def __init__(self, block_dict):
        self._block = block_dict


    def __getattr__(self, item):
        return self._block.get(item)


    def reply_to(self):
        """
        解析里面回复的id, 返回ids
        :return: list
        """
        return re.findall(r'No\.(\d+)', self.content)


    @property
    def image_url(self):
        """
        包含的image url
        :return:
        """
        if not self.image:
            return None
        return ''.join((CDNHOST, self.image))

    def replace_image_url(self, path):
        """
        替换里面的url标签的内容为cache的图片地址
        :param path:
        :return:
        """


def sanitize_url(url):
    from urllib import parse
    parts = parse.urlsplit(url)
    path = '/api' + parts.path
    return parse.urlunsplit((parts.scheme, parts.netloc, path, '',''))



async def run(first_url, loop):
    print('run!')
    p = await Page.from_url(first_url, page_num=1)
    while True:
        print('page go')
        thread_list = p.thread_list()
        for block in thread_list:
            if block.image_url:
                asyncio.ensure_future(image_manager.submit(block.image_url))
            print(block.uid, block.image_url, block.reply_to() or None)
        if p.has_next():
            p=await Page.from_url(*p.next_page_info)
        else:
            break
        if p.next_page_num > 1:
            break
    # asyncio.ensure_future(image_manager.inter_status_info())
    await image_manager.wait_all_task_done()




# first_url = input('url\n')
# first_url = 'http://h.nimingban.com/t/117617?page=10'
first_url = 'http://h.nimingban.com/t/7250124?page=123'
first_url = sanitize_url(first_url)

print('first url is', first_url)
loop = asyncio.get_event_loop()
image_manager = ImageManager(loop)
loop.create_task(run(first_url, loop))

loop.run_forever()

