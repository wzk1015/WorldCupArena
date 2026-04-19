1. 模型更新：Gemini只保留3 Pro和3 Flash，GPT用5.4。暂时不更新开源模型，因为没有足够的卡部署。保留接口和代码
2. 把s2b和s3b两个setting去掉，这样s0, s2a, s3a只测试LLM本身，只有S1是测试deep research agent。所以对于你提到的每种模型只需要测试其中的部分setting（例如closed/open LLM只测试s0, s2a, s3a，而search-enabled和deep research agent只测试s1）。你可以把这四个setting重新编号。并更新一下cost计算，说明这样可以省去多少花销
3. breakdown一下T1~T5分别的花销。另外如果T5仅在整个赛事前预测一次，或者只在赛事前、小组赛结束后分别预测一次，花销能降低多少
4. 要求模型先输出详细的reasoning，再输出每一项的预测
5. 模型预测时进行齐全完备的格式检查，以防赛后评分时解析错误
6. 支持更换LLM的base url以便使用中转



1. 每个provider只默认保留一个LLM（deepresearch agent不算），比如GPT保留5.4，claude是sonnet，gemini是gemini-3-pro，mirothinker是他们最新最强的。更新花销估算
2. 写一个运行脚本，以本周刚结束的拜仁皇马欧冠1/4决赛为例进行dryrun测试，结果泄露并不重要，主要为了把流程跑通
3. 写一个齐全但简单易懂的文档，说明如何运行程序来进行预测和评分。告诉我如何针对本周末的英超和其他联赛进行测试
4. 写一个用于输入给nano banana pro生成项目logo的prompt。不需要写调用脚本，我自己以后会写好
5. 写一个文档告诉LLM或者deepresearch agent的开发者，如何迅速将自己的模型接入benchmark进行评测
6. 写一个中文的宣传文案，分为比较长的公众号风格的版本、短的朋友圈风格的版本、中等的小红书风格的版本





Setting只保留两个：
1. 不联网LLM，直接提供squads + form + news + stats
2. 联网LLM/agent，通过提示模型自主搜索squads + form + news + stats，并提供这些信息的例子，并说明还可以自主搜索更多信息
并更新cost计算
另外两个暂时不想留：
3. 不联网LLM，不给任何信息
4. 联网LLM/agent，不进行任何提示，自主搜索

另外，news不要只是五条新闻的headline，最好是20条新闻的headline
还要增加鲁棒性处理，例如比赛结果fixture格式里如果某个event的时间（比如第几分钟换人）是无效的（<0），则评测时忽略时间；类似的有其他情况要handle；如果实在无法handle则忽略此条数据。注意只处理truth fixture缺失的情况，不考虑模型预测缺失


1.目前context_pack里news还是空的，想办法从某个API或者网站获取数据填进去，以辅助S1的模型推理
2.目前的github workflow如何自动化？是不是包括赛前获取fixture、预测、lock、获取truth、grade、leaderboard几个功能？写个文档详细说明
3.做一个项目网页展示leaderboard以及各个模型对于下一场比赛的预测，要做的有趣、fancy、有噱头一些。并且设计一下如何加入到自动化workflow中使得每场比赛前后自动更新

1.这个automation workflow如何输入secrets，比如yaml里要读取的api key
2.优化模型评测时S1和S2的prompt，提示模型要考虑的因素，比如球队和球员的综合水平、近期战绩和状态，两队交手历史，战术，队友之间配合和化学反应，球员和对手球员的交互，（再补充一些）
3.用最简单的话告诉我怎么运行workflow，怎么部署和访问网页



修改一下网站的显示，对于每个模型的预测（例如对于data/predictions/mls_lafc_test/gpt-5.4-search__S2.json，并参考schemas/prediction.schema.json）：
1. 比分显示最高概率的三个
2. 显示进球球员和概率
3. 最高概率的motm
4. reasoning默认多显示几行，并可以点击reasoning在同一页面内弹出一个框显示完整的reasoning（注意到这是一个字典，请通过比较好看的表格来呈现）
5. 可以点击按钮显示更多预测：lineups、进球球员的进球时间、助攻球员及时间、换人、红牌黄牌、点球、乌龙、stats等
另外：
1. 在页面最开始的某处增加作者信息和邮箱（Zhaokai Wang，zhaokaiwang99@gmail.com，主页https://www.wzk.plus），并把github链接（https://github.com/wzk1015/WorldCupArena/）加在更显眼的地方，而不仅仅是页面右上角现在这个
2. 把last updated从2026-04-19T20:51:54+00:00改成2026-04-19 20:51:54 (UTC+0)的格式
3. History这个部分的每个block默认是打开的
4. workflow由于是每10分钟更新一次的，请在每次workflow时获取已预测比赛的实时情况（类似于truth.json，但不要保存在这个位置以免影响其它代码），从而用于（且仅用于）在网页上显示正在进行的比赛的实时比分
5. 去掉s2-s1 uplift这个模块
6. 对于实时比赛和已结束比赛，要和未进行比赛的模型预测一样，显示出模型的所有预测，以及每一项对应的实际比赛结果

对于history，显示每一个预测的项对应的实际结果（从truth读取）