# DTL SGX Scraping

这是 DTL Data Engineer 的下一阶段测试，使用 Python 在 SGX 网站上下载指定日期的历史数据。
$$
\min_{w,b} \frac{1}{n} \sum_{i=1}^n L(y_i, w^T x_i + b) + \lambda \|w\|^2
$$

$$
\min_{w,b} \frac{1}{n} \sum_{i=1}^n L(y_i, w^T x_i + b) + \lambda \|w\|^2
$$

$$
L(y_i, \hat{y}_i) = \max(0, 1 - y_i \hat{y}_i)
$$



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

   HD, Tick, Trade Cancellation, Data Structure

2. **时间范围 (if not DS file) `range`**

   支持两种方式指定时间范围: 1) 开始日期 - [结束日期]; 2) 最近 n 天

3. **保存的位置 `save_path`**

   指定下载文件的保存位置。默认为当前目录，会在指定目录下新建文件夹 `/derivHistData` 保存.

4. **日志输出位置** `output_loc`

   默认将 `WARNING`, `ERROR` 输出至控制台，将 `INFO`, `WARNING`, `ERROR` 输出至文件中。即 `[['W', 'E'], ['I', 'W', 'E']]`。

5. **是否自动重新下载** `auto_retry`

   遇到下载不成功的文件，是立刻自动重新下载。还是在下载任务完成后，请求用户是否需要重新下载。默认为 `true`，重试 `max_retry` 后返回。

6. **最大重新下载次数 `max_retry`**

   下载不成功重试的次数。

### 2. Output

该程序需要使用 Python 自带的 Logging module 输出程序运行时的状态信息，包括：

1. [INFO] 运行阶段

   当前正在执行的任务，及进度。总共分为以下 2 个运行阶段：

   1. **初始化阶段**

      包括各种输入参数的校验、类对象的创建

   2. **数据下载阶段**

      接着，就可以通过这些参数发送相应的请求，下载文件。在完成后，显示 job summary. 等待用户指示是否需要重新下载未完成的文件。

2. [Warning] 文件下载失败

   具体见 3.2

3. [ERROR] config 参数错误

   具体见 3.1

### 3. Exception Handling

此外，还要考虑该程序在运行时可能产生的异常情况：

1. **用户交互异常**

   用户设置的参数可能有问题，包括格式上的，以及逻辑上的。需要确保输入参数合理、正确后，才能运行程序。

   -> 程序终止，指出参数错误的原因

2. **数据下载异常**

   在请求下载 url 后，如果服务器返回的不是 `200` 或者超过了 `timeout` 仍然没有返回，就应当抛出异常。

   -> 在 `max_retry` 内，再次重试下载

   最后，还需要进行文件完整性校验，检查实际的文件大小是否与预期的文件大小一致。



## II. Program Design

遵循软件工程的一般流程，在确认需求之后，就可以对软件进行顶层设计了。

### 1. Workflow

不妨先实现该软件的核心功能，下载指定日期范围内的文件，并显示进度条。在这一核心功能的基础上，再逐步扩充日志输出、参数设定、异常处理这些模块。

核心模块参考了[How To: Progress Bars for Python Downloads](https://www.alpharithms.com/progress-bars-for-python-downloads-580122/)，通过使用 `request` 和 `tqdm` 实现了从指定 url 以流式下载文件，并保存至用户指定的 `parentDir` 下的 `SAVE_DIR` 文件夹中。

下一步，使该程序支持参数设定，假定所有的 DS 文件均相同。

`restDay:` 经过我的观察，只有周末的数据不可用，其它时间段的数据均可用。因此，只需要取一个较早的周一，和它计算 `deltaDay`，判断取余 7 后，是否为 5/6 即可。如果是的话，直接跳过。

`BASE_DAY`: 选定 1000 个交易日之前的日子为基准日期，保存它的 `deltaday`. 从而可以通过数学公式计算出任意日期的 `deltaday`. 该公式为：

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
[datetime(2020, 2, 1), datetime(2020, 11, 13)]
```

特别地，`2022-11-13` 理论的位置发生了 404，ID 上移了 2 位至 `4768`。而 `2020-02-01` 和 `2020-11-14` 均是周六 (非交易日)，却有记录文件。

> **🚩优化点1: DS 文件是否相同**
>
> - 如果相同，在程序开跑时，一次性请求 DS 文件，然后忽略用户的请求，并给予提示；
> - 如果不同，需要分出相同的时间区间，将不同结构的数据文件放在不同的文件夹中。以方便后期的处理和分析。
>
> -> 可以先通过以 50 天为间隔进行遍历，两两比较文件内容是否相同。如果完全相同，再在每个 50 天的间隔内，随机抽取 10 天进行比较。如果仍完全相同，则基本可以确定所有的 DS 文件均相同。

接着，我们加入日志模块。





























