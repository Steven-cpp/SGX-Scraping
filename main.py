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
BAD_DATES = [datetime(2020, 2, 1), datetime(2020, 11, 13)]
base_url = "https://links.sgx.com/1.0.0/derivatives-historical/"
TYPE_DICT = {0: 'ALL', 1: 'HD', 2: 'TK', 3: 'TC', 4: 'DS'}
TYPE_NAME = ['WEBPXTICK_DT.zip', 'TC.txt', 'TK_structure.dat', 'TC_structure.dat']
tc_ds_url = f"{base_url}5361/TC_structure.dat"
tick_ds_url = f"{base_url}5361/TickData_structure.dat"


class Scraper:

    def __init__(self, config_file) -> None:
        # Load the logging configuration from file        
        with open(config_file, 'r') as f:
            config = json.load(f)
        logging.config.dictConfig(config['logging'])
        self.logger = logging.getLogger(__name__)
        self.logger.info('=====   Scraper Initializing   =====')
        self.logger.info('Logging   module successfully configured')
        self.batch_size = 0
        self.iter = 0
        self.excFiles= []
        self.excFileUrls = []
        self.MAX_RETRY = 3
        self.SAVE_DIR = './'
        self.logger.info('Scraping  module successfully configured')

    
    def getHistData(self, dtype, start, end):
        # [TODO: EXC] (private) Ensure the validity of `start` and `end`
        self.logger.info('===== Downloading History Data =====')
        if (dtype == 4):
            self.logger.info('DS already downloaded')
            return
        self.batch_size = self.__date2Deltadays(end) + 1 - self.__date2Deltadays(start)
        self.iter = 1
        self.iter_exc = 0
        if (dtype in [0, 1]):
            self.batch_size *= 2

        for i in range(self.__date2Deltadays(start), self.__date2Deltadays(end) + 1):
            tc_url = f"{base_url}{i}/TC.txt"
            tick_url = f"{base_url}{i}/WEBPXTICK_DT.zip"
            if (dtype in [0, 1, 2]):
                self.__downloadFromUrl(tick_url, self.SAVE_DIR)
            if (dtype in [0, 1, 3]):
                self.__downloadFromUrl(tc_url, self.SAVE_DIR)
        
        n_success = self.batch_size - len(self.excFiles)
        logging.info(f'Successfully downloaded {n_success} files; {len(self.excFiles)} files failed')

        if len(self.excFiles) > 0:
            logging.warning('Failed files: ' + str(self.excFiles))
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
    def __downloadFromUrl(self, url, parent_dir, isRetry=False):
        SAVE_DIR = "histData"
        emsg = None

        # [TODO: FT] Make it private and ensure the validity of input args 
        fileId = url[len(base_url): len(base_url) + 4]
        fname_exp = url[len(base_url) + 5:]
        fname_exp = fname_exp[:-4] + '-' + fileId + fname_exp[-4:]
        
        if (not os.path.exists(parent_dir)):
            print(f"ERROR: path '{parent_dir}' NOT EXISTS")
            exit(-1)
        dir = os.path.join(parent_dir, SAVE_DIR)

        try:
            with requests.get(url, stream=True, timeout=5) as r:
                # check header to get content length, in bytes
                size_expected = int(r.headers.get("Content-Length"))
                if (r.headers.get('Content-Disposition') is None):
                    raise RequestException('404, requested file NOT FOUND')
                _, fname = r.headers['Content-Disposition'].split(';')
                fname = fname.replace('filename=', '').strip('"') 

                # implement progress bar via tqdm
                with tqdm.wrapattr(r.raw, "read", total=size_expected, desc="")as raw:    
                    with open(f'{dir}{os.path.sep}{fname}', 'wb')as output:
                        shutil.copyfileobj(raw, output)
            self.logger.info(f'{self.iter}/{self.batch_size}: {fname_exp} saved to {parent_dir}{SAVE_DIR}')
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
        for (id, url) in enumerate(self.excFileUrls):
            logging.info(f'{id + 1}/{len(self.excFiles)}: Redownloading {self.excFiles[id]}')
            for i in range(self.MAX_RETRY):
                emsg = self.__downloadFromUrl(url, self.SAVE_DIR, isRetry=True)
                if(emsg is None):
                    logging.info(f'\t{i + 1}/{self.MAX_RETRY} attemp success')
                else:
                    logging.info(f'\t{i + 1}/{self.MAX_RETRY} attemp failed: {emsg}')




    # Convert `date` to days in SGX Derivitive hist data
    def __date2Deltadays(self, date: datetime) -> int:
        # [TODO: EXC] returned days could be out of range
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
            res_date -= timedelta(days=1)
        if (res_date >= BAD_DATES[1]):
            res_date -= timedelta(days=4)
        return res_date


if __name__ == "__main__":
    start = datetime(2023, 3, 3)
    end = datetime(2023, 3, 10)
    s = Scraper('config.json')
    s.getHistData(1, start, end)
    
    
    


