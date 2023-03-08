import requests
import shutil
from tqdm.auto import tqdm
import os
from requests.exceptions import RequestException
from datetime import datetime, timedelta
import logging
import logging.config
import json


BASE_DATE = datetime(2019, 5, 6)
BASE_DELTA = 4366
MAX_DELTA_RANGE = 1000
DELTA_LEN = 4
BAD_DATES = [datetime(2020, 2, 1), datetime(2020, 11, 13)]
BAD_DELTA = 4766
base_url = "https://links.sgx.com/1.0.0/derivatives-historical/"
TYPE_DICT = {0: 'ALL', 1: 'HD', 2: 'TK', 3: 'TC', 4: 'DS'}
TYPE_NAME = ['WEBPXTICK_DT.zip', 'TC.txt', 'TK_structure.dat', 'TC_structure.dat']
tc_ds_url = f"{base_url}5361/TC_structure.dat"
tick_ds_url = f"{base_url}5361/TickData_structure.dat"

"""
A simple scraper to download historical trading data in given time range

Configs
-------
DTYPE : int ->> range(0, 5)
    kind of statistics to scrape
START, END : datetime ->> between 2019-05-06 AND Today(2023-03-07)
    target time range, can be `None` ONLY when `LATEST_N` set
LATEST_N : int ->> range(1, 1000)
    last n trading days, can be `None` ONLY when `START` and `END` set
MAX_RETRY : int -> range(1, 5)
    max retry attempts when download failed, 3 by default
ROOT_PATH : str -> os.path.exists()
    root path of saved scraped files, cwd by default.
    noted the final save_path is `{ROOT_PATH}/{PARENT_DIR}`
PARENT_DIR : str -> os.mkdir() can succeed
    parent dir of scraped files, 'histData' by default
AUTO_RETRY : bool -> [NO constraint]
    whether automatically redownload recorded failed files:
        * True : redownload failed files at the end of the job
        * False: await further user instruction when the job finished

"""
class Scraper:

    def __init__(self, config_file) -> None:
        # Load the logging configuration from file        
        with open(config_file, 'r') as f:
            config = json.load(f)
        logging.config.dictConfig(config['logging'])
        self.config_path = config_file
        self.logger = logging.getLogger(__name__)
        self.logger.info('=====   Scraper Initializing   =====')
        self.logger.info('Logging   module successfully configured')

        downloadArgs = config['download']
        self.DTYPE = downloadArgs['type']
        self.START = downloadArgs['start']
        self.END = downloadArgs['end']
        self.LATEST_N = downloadArgs['latest_n']
        self.MAX_RETRY = downloadArgs.get('max_retry', 3)
        self.ROOT_PATH = downloadArgs.get('root_path', "./")
        self.PARENT_DIR = downloadArgs.get('parent_dir', "histData")
        self.AUTO_RETRY = downloadArgs.get('auto_retry', False)
        self.__checkInputArgs()

        self.batch_size = 0
        self.iter = 0
        self.excFiles= []
        self.excFileUrls = []
        self.logger.info('Download  module successfully configured')
        self.logger.info('Scraper Initialized')

    
    def getHistData(self):
        self.logger.info('===== Downloading History Data =====')
        if (self.DTYPE == 4):
            self.logger.info('DS already downloaded')
            return
        deltaRange = range(self.__date2Deltadays(self.START), self.__date2Deltadays(self.END) + 1)
        self.batch_size = deltaRange[-1] - deltaRange[0] + 1
        if (BAD_DELTA in deltaRange):
            self.batch_size -= 1
        self.iter = 1
        self.iter_exc = 0
        if (self.DTYPE in [0, 1]):
            self.batch_size *= 2

        for i in deltaRange:
            if (i == BAD_DELTA):
                continue
            tc_url = f"{base_url}{i}/{TYPE_NAME[1]}"
            tick_url = f"{base_url}{i}/{TYPE_NAME[0]}"
            if (self.DTYPE in [0, 1, 2]):
                self.__downloadFromUrl(tick_url)
                    
            if (self.DTYPE in [0, 1, 3]):
                self.__downloadFromUrl(tc_url)
        
        n_success = self.batch_size - len(self.excFiles)
        logging.info(f'Successfully downloaded {n_success} files; {len(self.excFiles)} files failed')

        if len(self.excFiles) > 0:
            logging.warning('Failed files: ' + str(self.excFiles))
            if (self.AUTO_RETRY):
                self.__retryFailed()
                return
            doRetry = input('Do you want to retry downloading failed files? (Y/YES do retry): ')
            if (doRetry == 'Y' or doRetry == 'YES'):
                logging.info('User choose to retry failed files')
                self.__retryFailed()
            else:
                logging.info('User choose NOT to retry failed files')
        

    """
    Download file from `url` using a streaming GET request, tracked with proress bar.

    Parameter
    ---------
    url : str
        download link of target file
    parent_dir='./' : str
        target file will be saved under {parentdir}/{SAVE_DIR}
        ERROR, if `parent_dir` not exists
    """
    def __downloadFromUrl(self, url, isRetry=False):
        emsg = None
        fileId = url[len(base_url): len(base_url) + DELTA_LEN]
        tarDate = self.__deltadays2Date(int(fileId)).strftime('%Y%m%d')
        fname_exp = url[len(base_url) + DELTA_LEN + 1:]
        fname_exp = fname_exp[:-DELTA_LEN] + '-' + tarDate + fname_exp[-DELTA_LEN:]
        dir = os.path.join(self.ROOT_PATH, self.PARENT_DIR)

        try:
            with requests.get(url, stream=True, timeout=5) as r:
                # check header to get file size, in bytes
                size_expected = int(r.headers.get("Content-Length"))
                if (r.headers.get('Content-Disposition') is None):
                    raise RequestException('404, requested file NOT FOUND')
                _, fname = r.headers['Content-Disposition'].split(';')
                fname = fname.replace('filename=', '').strip('"')

                # implement progress bar via tqdm
                with tqdm.wrapattr(r.raw, "read", total=size_expected, desc="")as raw:    
                    with open(f'{dir}{os.path.sep}{fname}', 'wb')as output:
                        shutil.copyfileobj(raw, output)
            self.logger.info(f'{self.iter}/{self.batch_size}: {fname_exp} saved to {dir}')
        except RequestException as e:
            emsg = e
            if (not isRetry):
                self.excFiles.append(fname_exp)
                self.excFileUrls.append(url)
                self.logger.debug(f'Failed to access {url}: {e}', exc_info=False)
                self.logger.warning(f'{self.iter}/{self.batch_size} failed: {fname_exp}: {e}')
           
        self.iter += 1
        return emsg


    def __retryFailed(self):
        logging.info('===== Redownload Failed Files =====')
        n_fails = len(self.excFiles)
        for (id, url) in enumerate(self.excFileUrls):
            logging.info(f'{id + 1}/{n_fails}: Redownloading {self.excFiles[id]}')
            for i in range(self.MAX_RETRY):
                emsg = self.__downloadFromUrl(url, isRetry=True)
                if(emsg is None):
                    logging.info(f'\t{i + 1}/{self.MAX_RETRY} attemp success')
                else:
                    logging.info(f'\t{i + 1}/{self.MAX_RETRY} attemp failed: {emsg}')
        logging.info(f'Successfully redownloaded {n_fails - len(self.excFiles)} files; {len(self.excFiles)} files still failed')
        pass


    # Convert `date` to days in SGX Derivitive hist data
    def __date2Deltadays(self, date: datetime) -> int:
        days_passed = (date - BASE_DATE).days
        n_rest = days_passed // 7 * 2
        rem = days_passed % 7
        if (rem < 5):
            delta_cur = BASE_DELTA + days_passed - n_rest
        else:
            delta_cur = BASE_DELTA + days_passed - n_rest - rem + 4
            # print('==== Is Weekend ====')
        if (date >= BAD_DATES[0]):
            delta_cur += 1
        if (date >= BAD_DATES[1]):
            delta_cur += 2
        return delta_cur
    

    def __deltadays2Date(self, days: int) -> datetime:
        # [TODO: BUG] Mapping consistency with date <-> deltaDays, especially around BAD_DATES
        n_diff = days - BASE_DELTA
        rest_days = n_diff // 5 * 2
        res_date = BASE_DATE + timedelta(days=rest_days+n_diff)
        if (res_date >= BAD_DATES[0]):
            rest_days -= 1
        if (days >= BAD_DELTA):
            if (days == BAD_DELTA):
                logging.error('accessed bad delta')
            elif (days != BAD_DELTA + 1):
                rest_days -= 2

            if (n_diff % 5 in [0, 1, 2]):
                rest_days -= 2

        return BASE_DATE + timedelta(days=rest_days+n_diff)


    """
    Check the validity of input arguments, as stated in the class doc
    """
    def __checkInputArgs(self):
        logging.info('checking download module configs...')
        try:
            if not isinstance(self.DTYPE, int) and self.DTYPE in range(0, 5):
                raise ValueError('DTYPE should be of type `int` and within [0, 5)')

            if self.LATEST_N:
                if not (isinstance(self.LATEST_N, int) and self.LATEST_N < MAX_DELTA):
                    raise ValueError(f'LATEST_N should be of type `int` and < {MAX_DELTA}')
                self.useRange = False
            elif self.START and self.END:
                self.START = datetime.strptime(self.START, '%Y-%m-%d')
                self.END = datetime.strptime(self.END, '%Y-%m-%d')
                if self.START >= self.END:
                    raise ValueError('START date should be earlier than END date')
                if self.START < BASE_DATE:
                    raise ValueError(f'START date should be after {datetime.strftime(BASE_DATE, "%Y-%m-%d")}')
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                if self.END >= today:
                    raise ValueError(f'END date should be earlier than today ({datetime.strftime(today, "%Y-%m-%d")})')
                self.useRange = True
            else:
                raise ValueError('time range incomplete, please specify LATEST_N or [START, END]')
            
            if not (isinstance(self.MAX_RETRY, int) and self.MAX_RETRY in range(1, 5)):
                raise ValueError('MAX_RETRY should be of type `int` and within [1, 5)')
            
            if not os.path.exists(self.ROOT_PATH):
                raise ValueError(f'ROOT_PATH {self.ROOT_PATH} not exists')
            
            if isinstance(self.PARENT_DIR, str):
                dir = os.path.join(self.ROOT_PATH, self.PARENT_DIR)
                if not os.path.exists(dir):
                    os.mkdir(dir)
                    logging.info(f'created new directory `{self.PARENT_DIR}` under {self.ROOT_PATH}')
            
        except (ValueError, OSError) as e:
            logging.error(f'Invalid Configuration: {e}', exc_info=True)
            logging.info(f'Check {self.config_path} to fix this error')
            exit(-1)
        
    """
    Find mapping inconsistency, and try to fix it.

    0. suppose dates -> delta is safe, try to fix delta -> dates
    1. every 50 days, show the `expected` and `output` dates


    """    
    def __deltaMappingTest():
        pass

            
        


if __name__ == "__main__":
    start = datetime(2023, 3, 3)
    end = datetime(2023, 3, 10)
    s = Scraper('config.json')
    s.getHistData()
    
    
    


