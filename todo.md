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