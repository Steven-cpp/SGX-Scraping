# DTL SGX Scraping

这是 DTL Data Engineer 的下一阶段测试，使用 Python 在 SGX 网站上下载指定日期的历史数据。

## I. Requirement

Design a job to download the following files daily from the above website:

1. WEBPXTICK_DT-*.zip
2. TickData_structure.dat
3. TC_*.txt
4. TC_structure.dat

As is shown in the following snapshot, each file corresponds to each drop down options in *Time and Sales Historical Data*.

![image-20230306093101769](https://raw.githubusercontent.com/Steven-cpp/myPhotoSet/main/image-20230306093101769.png)

Send us a **.tar.gz** or **.zip** file that contains all the relevant files that you would like to submit.

由于需求文档的说明非常 general，自由度非常大，因此我结合实际的使用需求，将程序的规约进一步的细化。

### 1. Input

该程序可以用命令行运行，并指定通过 `config` 文件指定参数，这些参数包括：

1. **下载的数据类型 `type`**

   ALL, Both, Tick, Trade Cancellation, Data Structure

2. **时间范围 (if not DS file) `range`**

   支持两种方式指定时间范围: 1) 开始日期 - [结束日期]; 2) 最近 n 个交易日

3. **保存的位置 `root_path`**

   指定下载文件的保存根位置，默认为当前目录。

4. **父文件夹** `parent_dir`

   会在 `root_path` 目录下新建文件夹 `parent_dir` 保存。即最终的存储路径位 `root_path/parent_dir`。

5. **日志输出位置** `output_loc`

   默认将 `INFO` 及以上输出至控制台，将 `DEGUG` 及以上输出至文件中。

6. **是否自动重新下载** `auto_retry`

   在下载结束后，是自动重新下载失败的文件，还是请求用户是否需要重新下载。默认为 `false`，重试 `max_retry` 后返回。

7. **最大重新下载次数 `max_retry`**

   下载不成功重试的次数。

### 2. Output

该程序需要使用 Python 自带的 Logging module 输出程序运行时的状态信息，包括：

1. [INFO] 运行阶段

   当前正在执行的任务，及进度。总共分为以下 3 个运行阶段：

   1. **初始化阶段**

      包括各种输入参数的校验、类对象的创建

   2. **文件下载阶段**

      接着，就可以通过这些参数发送相应的请求，下载文件。对于下载的每个文件，都会显示其下载进度，并且返回其成功或失败的信息。

      在所有任务下载完成后，显示 job summary，等待用户指示是否需要重新下载未完成的文件。

   3. **重新下载阶段**

      如果有文件下载异常，并且用户指定重新下载，则会进入该阶段。重新下载记录下来的异常文件。

2. [Warning] 文件下载失败

   具体见 3.2

3. [ERROR] config 参数错误

   具体见 3.1

### 3. Exception Handling

此外，还要考虑该程序在运行时可能产生的异常情况：

1. **用户交互异常**

   用户设置的参数可能有问题，包括格式上的，以及逻辑上的。需要确保输入参数合理、正确后，才能运行程序。

2. **数据下载异常**

   在请求下载 url 后，如果服务器返回的不是 `200` 或者超过了 `timeout` 仍然没有返回，就应当抛出异常。

## II. Program Design

遵循软件工程的一般流程，在确认需求之后，就可以对软件进行顶层设计了。

不妨先实现该软件的核心功能，下载指定日期范围内的文件，并显示进度条。在这一核心功能的基础上，再逐步扩充日志输出、参数设定、异常处理这些模块。

### 1. Core Module

核心模块参考了[How To: Progress Bars for Python Downloads](https://www.alpharithms.com/progress-bars-for-python-downloads-580122/)，通过使用 `request` 和 `tqdm` 实现了从指定 url 以流式下载文件，并保存至用户指定的 `root_path` 下的 `parent_dir` 文件夹中。

由于每个文件在服务器上都对应着一个文件 ID，又可以通过该 ID 生成该文件的下载链接，只需要通过 `request.get(url)` 便可下载该文件。但是用户输入的是 `date`，而不是 `fileId`，因此需要确定两者的映射关系。

**date -> fileId**

我先是猜测，应当是交易日 `buis_day` 才会产生该数据文件，所有的周末、节假日 `resr_day` 应当都会被跳过。于是，我下载了最近 100 天的文件来验证这一猜想。但经过我的观察，只有周末的数据不可用，其它时间段的数据均可用。因此，只需要取一个最早的周一作为 `BASE_DAY` ，和它计算 `passed_day`，判断取余 7 后，是否为 5/6 (周末) 即可。如果是的话，直接跳过。

于是，我选定了大概 1000 个交易日之前的周一作为基准日期，将其定义为 `BASE_DAY`，用户选定的开始日期不得早于 `BASE_DAY`。从而可以通过以下的公式，计算出任意日期的 `deltaDay` 也就是 `fileId`:

```python
days_passed = tarDay - BASE_DAY
n_rest = days_passed / 7 * 2
rem = days_passed % 7
if (rem < 5):
	delta_cur = delta_base + tarDay - BASE_DAY - n_rest
else:
  delta_cur = delta_base + tarDay - BASE_DAY - n_rest - rem + 4
```

但事实上，服务器中的 `delta_days` 存在异常点，并不是如理论中的那么连续、规律。经过长达 1 小时的尝试，我找到了 2 个异常点，如下:

```python
BAD_DATES = [datetime(2020, 2, 1), datetime(2020, 11, 13)]
```

特别地，`2020-11-13` 的理论位置产生了空缺，ID 上移了 2 位至 `4768`。而 `2020-02-01` 和 `2020-11-14` 均是周六 (非交易日)，却有记录文件。

从而，针对这两个时间点，还需要特殊处理。由于 `2020-02-01` 是周六，但是有交易记录文件。于是，在该天及之后的日期 `delta_days` 需要 +1，表示多了一个交易日。而对于 `2020-11-13`，又产生了空缺，又在周六有交易记录，因此需要 +2，表示多了一个交易日，还要补齐一个交易日的空缺。

最终，可以得到由 `date` 向 `deltaDays` 的映射函数:

```python
def date2Deltadays(date: datetime) -> int:
  """
  Convert `date` to days(fileId) in SGX Derivitive hist data

  Noted
  -----
  It converts weekend to last Friday. So when weekend is set as start date, 
  it is implicitly perceived as last friday.
  """
  days_passed = (date - BASE_DATE).days
  n_rest = days_passed // 7 * 2
  rem = days_passed % 7
  if (rem < 5):
    delta_cur = BASE_DELTA + days_passed - n_rest
  else:
    delta_cur = BASE_DELTA + days_passed - n_rest - (rem - 4)

  if (date >= BAD_DATES[0]):
    delta_cur += 1
  if (date >= BAD_DATES[1]):
    delta_cur += 2
  return delta_cur
```

至此，核心模块的实现已经基本完成。

### 2. Logging Module

接下来，为当前的程序添加日志模块。To isolate and organize the logging logic, I decided to **refactor my functions in an object-oriented manner**. So that I can encapsulate logging logic within a class, controling when, where, and how logs are generated, and ensure that they are consistent across this scraper.

This can be implemented by simply importing `logging` module, and set up `logger` instance within the class from user specified config file. By default, the level of the file handler is set to `DEBUG` and the level of the console handler is set `INFO`, which means only levels >= `INFO` will show up on the console, while levels  >= `DEBUG` will be written to the log file.

A typical log file looks like the  following (with the year-month-date removed):

```python
10:14:06 - __main__ - INFO - =====   Scraper Initializing   =====
10:14:06 - __main__ - INFO - Logging module successfully configured
10:14:06 - root - INFO - checking download module configs...
10:14:06 - __main__ - INFO - Download module successfully configured
10:14:06 - __main__ - INFO - Done! Scraper Initialized
10:14:06 - __main__ - INFO - =====   Download History Data  =====
10:14:06 - __main__ - INFO - Job Overview:
10:14:06 - __main__ - INFO -    Date Range : from 2023-02-24 to 2023-03-09
10:14:06 - __main__ - INFO -    Data Type  : ALL
10:14:06 - __main__ - INFO -    Total Nums : 22
10:14:06 - __main__ - INFO -    Save Dir   : /Users/shiqi/Desktop/Projects/Seeking Job/Projects/histData
10:14:07 - __main__ - INFO - downloading structural data
10:14:07 - __main__ - INFO - 1/22: TC_structure.dat already downloaded
10:14:07 - __main__ - INFO - 2/22: TickData_structure.dat already downloaded
10:14:07 - __main__ - INFO - downloading history data
10:14:07 - __main__ - INFO - 3/22: WEBPXTICK_DT-20230224.zip already downloaded
10:14:07 - __main__ - INFO - 4/22: TC_20230224.txt already downloaded
...
10:14:07 - root - INFO - Successfully downloaded 22 files; 0 files failed
10:14:07 - root - INFO - Done! Complete downloading history data.
```

It consists of three stages, as is outlined in I.2

### 3. Error Recovery

This program may encounter two types of errors: configuration errors and download errors, as is outlined in I.3.

Configuration errors are classified as `ERROR` since they are unrecoverable until the user fixes the configuration. To prevent such errors, the program strictly checks all configurations during the scraper initialization stage, verifying both their type and logic. Once, invalid argument is detected, the program will send error message, and then exit.

While download errors are classified as `WARNING`, since in most cases, they are recoverable, resolved by re-downloading failed files. When such exception occurs, the program records the failed files and awaits user instruction to redownload them at the end of the job.

### 4. Optimization

To further enhance the user experience and program efficiency, I have come up with three new features to add to this program:

1. **Latest N Days**

   I have implemented a feature that allows users to specify a time range using the 'latest_n' day format. This feature makes it easier for users to retrieve data from specific time periods without having to manually sift through the data themselves. With this feature, users can simply specify the number of days they want to retrieve data from, and the program will automatically retrieve the relevant data.

2. **Avoid DS File Redundancy**

   After comparing data structure (DS) files on 20 different days on the server, I discovered an interesting fact: they are all the same. And the downloaded DS file has no date suffix. As a result, I established that DS files on different dates are the same.

   Based on this insight, I optimized DS file downloads by downloading only one pair of DS files in the beginning, independent of the time range. This feature not only saves time and bandwidth by avoiding redundant attempts, but it also ensures that users are always getting the most up-to-date version of the data.

3. **File Exsistence Check**

   Finally, I added a file existence check feature that prevents the program from attempting to download a file that already exists. This feature helps to eliminate duplicate files and saves time by avoiding unnecessary downloads.

With these three features, this program might be more efficient and user-friendly.



















