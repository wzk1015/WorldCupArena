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