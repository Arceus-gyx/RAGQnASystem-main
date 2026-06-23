# 医疗 KG-RAG 问答系统核心技术方案

## 1. 项目定位

本项目是一个基于 `Streamlit + Neo4j + BERT/RoBERTa + Qwen API + Qdrant` 的医疗领域 Hybrid RAG 问答系统。

系统目标是降低大模型在医疗问答中的幻觉风险。用户提问后，系统不会直接让大模型自由回答，而是先从结构化医疗知识图谱和非结构化医学文档中检索证据，再把证据交给大模型生成最终回答。

整体链路：

```text
用户问题
 -> 医疗实体识别 NER
 -> 大模型意图识别
 -> Neo4j 知识图谱检索
 -> Qdrant 向量检索
 -> 证据融合 Prompt
 -> Qwen API 生成回答
 -> Streamlit 展示
```

## 2. 系统核心模块

项目主要分为 6 个模块：

```text
1. Streamlit 前端界面
2. 用户登录/注册模块
3. 医疗实体识别 NER 模块
4. Neo4j 医疗知识图谱模块
5. Qdrant 向量文档检索模块
6. 大模型意图识别与回答生成模块
```

核心文件：

```text
login.py                 登录/注册入口
user_data_storage.py     用户数据存储
webui.py                 主问答界面和 RAG 流程
ner_data.py              NER 数据集构造
ner_model.py             NER 模型训练和推理
build_up_graph.py        Neo4j 知识图谱构建
vector_rag/              Qdrant 向量检索模块
ingest_docs.py           文档导入 Qdrant 脚本
```

## 3. 前端与用户系统

前端使用 `Streamlit` 实现，启动入口：

```powershell
streamlit run login.py
```

`login.py` 负责登录和注册页面。登录成功后调用 `webui.py` 中的：

```python
main(is_admin, usname)
```

用户信息存储在：

```text
tmp_data/user_credentials.json
```

`user_data_storage.py` 中定义了 `Credentials` 类：

```python
username
password
is_admin
```

默认管理员账号：

```text
admin / admin123
```

普通用户与管理员区别：

```text
普通用户：进行医疗问答
管理员：查看实体识别结果、意图识别结果、知识库检索结果、向量检索结果，并导入医学文档到 Qdrant
```

管理员模式主要用于系统调试和知识库维护。

## 4. 医疗实体识别 NER

NER 的作用是从用户问题中识别医疗实体。

示例：

```text
问题：胃溃疡患者可以用阿司匹林吗？
实体：胃溃疡 -> 疾病，阿司匹林 -> 药品
```

相关文件：

```text
ner_data.py   构造 NER 训练数据
ner_model.py  定义 NER 模型和推理逻辑
```

### 4.1 NER 数据构造

`ner_data.py` 的核心流程：

```text
读取 data/ent_aug/ 下的实体词典
 -> 为每类实体构建 Aho-Corasick 自动机
 -> 遍历 medical.json 中的疾病简介、病因、预防文本
 -> 用自动机做字符串匹配
 -> 按 BIO 格式生成标签
 -> 写入 data/ner_data_aug.txt
```

支持的实体类型包括：

```text
疾病
疾病症状
检查项目
科目
食物
药品商
治疗方法
药品
```

BIO 标注示例：

```text
阿 B-药品
司 I-药品
匹 I-药品
林 I-药品
```

### 4.2 NER 模型结构

`ner_model.py` 使用：

```text
Chinese RoBERTa / BERT
+ BiLSTM
+ Linear 分类层
```

模型流程：

```text
输入文本
 -> BertTokenizer
 -> BertModel 得到上下文向量
 -> BiLSTM 捕捉序列上下文
 -> Linear 层预测每个 token 的 BIO 标签
```

项目还结合了：

```text
1. Aho-Corasick 规则匹配
2. TF-IDF 实体对齐
3. 实体替换、实体遮盖、实体拼接等数据增强
```

面试表达：

> NER 模块不是只依赖模型预测，而是结合词典规则和 TF-IDF 实体对齐，目的是让识别出的实体尽量和 Neo4j 知识图谱中的标准实体名称保持一致。

## 5. Neo4j 医疗知识图谱

Neo4j 用于存储结构化医疗知识，构建脚本：

```text
build_up_graph.py
```

主要数据来源：

```text
data/medical_new_2.json
```

图谱实体类型：

```text
疾病
药品
食物
检查项目
科目
疾病症状
治疗方法
药品商
```

典型关系：

```text
疾病 -> 疾病的症状 -> 症状
疾病 -> 疾病使用药品 -> 药品
疾病 -> 疾病宜吃食物 -> 食物
疾病 -> 疾病忌吃食物 -> 食物
疾病 -> 疾病所需检查 -> 检查项目
疾病 -> 疾病所属科目 -> 科目
疾病 -> 治疗的方法 -> 治疗方法
药品商 -> 生产 -> 药品
```

图谱构建流程：

```text
读取 medical_new_2.json
 -> 提取疾病属性、实体、关系
 -> 创建 Neo4j 节点
 -> 创建 Neo4j 关系
 -> 同时生成 data/ent_aug/ 和 data/rel_aug.txt
```

构建命令：

```powershell
python build_up_graph.py --website http://localhost:7474 --user neo4j --password 12345678 --dbname neo4j
```

问答阶段，系统根据实体和意图拼接 Cypher 查询。

示例：

```cypher
match (a:疾病{名称:'感冒'})-[r:疾病使用药品]->(b:药品)
return b.名称
```

查询结果会被包装为 `<提示>...</提示>`，加入最终 Prompt。

## 6. 大模型意图识别

项目没有训练单独的意图分类模型，而是使用大模型 Prompt 做意图识别。

入口：

```text
webui.py -> Intent_Recognition(query, choice)
```

系统会让大模型从预定义意图中选择用户问题对应的查询类型。

主要意图：

```text
查询疾病简介
查询疾病病因
查询疾病预防措施
查询疾病治疗周期
查询治愈概率
查询疾病易感人群
查询疾病所需药品
查询疾病宜吃食物
查询疾病忌吃食物
查询疾病所需检查项目
查询疾病所属科目
查询疾病的症状
查询疾病的治疗方法
查询疾病的并发疾病
查询药品的生产商
```

目前大模型调用已经从本地 Ollama 改成 Qwen OpenAI 兼容接口：

```python
qwen_chat_completion(prompt, model=choice)
```

支持模型：

```text
qwen-plus
qwen-turbo
```

面试表达：

> 意图识别采用 Prompt-based 方法，而不是传统分类模型，是为了减少人工标注意图数据的成本，同时支持多意图识别。例如“感冒了怎么办”可能同时涉及疾病简介、治疗方法、所需药品和检查项目。

## 7. Qdrant 向量检索模块

这是新增的 Hybrid RAG 部分，用于支持医学 PDF/TXT 文档检索。

新增目录：

```text
vector_rag/
```

文件职责：

```text
config.py          Qdrant 地址、collection、embedding 模型、chunk 参数
loaders.py         读取 PDF / TXT
text_splitter.py   文本切分 chunk
qdrant_store.py    Qdrant 初始化、embedding、写入、检索
document_ingest.py 文档导入流程封装
```

依赖：

```text
qdrant-client
sentence-transformers
pypdf
```

配置：

```python
QDRANT_URL = "http://localhost:6333"
QDRANT_COLLECTION = "medical_docs"
EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384
```

文档导入流程：

```text
PDF/TXT
 -> 文本读取
 -> 文本清洗
 -> chunk 切分
 -> sentence-transformers 生成 embedding
 -> 写入 Qdrant collection
```

命令行导入：

```powershell
python ingest_docs.py tmp_data/test_medical.txt
```

也支持管理员在 Streamlit 侧边栏上传 PDF/TXT，点击“写入向量库”。

查询流程：

```text
用户问题
 -> 生成 query embedding
 -> Qdrant 相似度检索
 -> 返回 top_k 文档片段
 -> 格式化为 [Vector 1] source=xxx, score=xxx
 -> 拼入最终 prompt
```

## 8. Hybrid RAG 融合逻辑

现在系统是：

```text
Neo4j Graph RAG + Qdrant Vector RAG
```

Neo4j 适合：

```text
疾病有哪些症状？
疾病需要做哪些检查？
某药品的生产商是谁？
疾病推荐哪些治疗方法？
```

Qdrant 适合：

```text
医学 PDF 指南
药品说明书
医学科普文章
临床规范文本
```

最终融合方式：

```text
Neo4j 检索结果
+ Qdrant 检索到的医学文档片段
-> 一起拼入 Prompt
-> 交给 Qwen API 生成最终回答
```

Qdrant 检索结果格式：

```text
<提示>
以下是从医学文档向量库检索到的补充资料：
[Vector 1] source=test_medical.txt, score=0.83
...
</提示>
```

这样大模型回答时既能参考图谱事实，也能参考医学文档片段。

## 9. 完整问答流程

以问题为例：

```text
胃溃疡患者可以用阿司匹林吗？
```

内部流程：

```text
1. Streamlit 接收用户问题
2. Qwen API 做意图识别
3. NER 模型识别疾病、药品等实体
4. 根据实体和意图查询 Neo4j
5. 同时调用 Qdrant 做向量检索
6. 将 Neo4j 结果和 Qdrant 文档片段合并进 Prompt
7. Qwen API 根据证据生成最终回答
8. 管理员可以查看实体识别、意图识别、图谱检索和向量检索结果
```

## 10. 项目亮点

```text
1. 不是简单 ChatBot，而是基于医学知识库的 RAG 系统。
2. 同时支持结构化知识图谱检索和非结构化文档向量检索。
3. NER 使用 BERT/RoBERTa + BiLSTM，并结合规则和 TF-IDF 实体对齐。
4. 意图识别使用大模型 Prompt，降低人工标注成本。
5. Neo4j 负责精确医学关系查询，Qdrant 负责语义相似文档召回。
6. Streamlit 提供管理员调试视图，可以查看中间检索链路。
7. 本地知识库和 API 大模型解耦，方便替换模型和部署。
```

## 11. 面试高频问题

### 为什么要用 Neo4j，而不是只用向量数据库？

Neo4j 适合表达明确的实体关系，比如疾病-症状、疾病-药品、药品-生产商。这类关系查询要求准确性，向量检索可能召回语义相似但关系不精确的文本。知识图谱可以提供更可控、更结构化的事实依据。

### 为什么还要加 Qdrant？

Neo4j 依赖提前抽取好的实体和关系，覆盖范围有限。医学 PDF、说明书、指南这类非结构化资料不一定适合全部结构化入图，因此用 Qdrant 做语义检索补充，可以提升知识覆盖率。

### Hybrid RAG 的优势是什么？

图谱检索保证精确关系，向量检索补充语义上下文，两者结合可以兼顾准确性和覆盖率。尤其在医疗问答里，单靠大模型容易幻觉，单靠图谱又可能知识不足，Hybrid RAG 更稳。

### 系统怎么减少幻觉？

最终 prompt 明确要求模型基于 `<提示>` 中的知识回答。如果 Neo4j 和 Qdrant 都没有相关证据，系统会要求回答“根据已知信息无法回答该问题”，从而减少自由发挥。

### 为什么把 Ollama 改成 Qwen API？

原项目默认本地 Ollama，但本地大模型对硬件要求高。改成 Qwen API 后，普通电脑也能复现系统，同时保留本地 NER、Neo4j、Qdrant 知识库。这样部署成本更低，也便于演示。

## 12. 面试总结版

这个项目是一个医疗领域 Hybrid RAG 问答系统。前端使用 Streamlit，知识库由 Neo4j 医疗知识图谱和 Qdrant 向量数据库组成。用户提问后，系统先用 BERT/RoBERTa-BiLSTM 做实体识别，再用 Qwen API 做意图识别。随后根据识别出的实体和意图查询 Neo4j，获得结构化医学知识；同时用 sentence-transformers 对问题生成 embedding，在 Qdrant 中检索相关医学文档片段。最后把图谱结果和向量检索结果一起拼入 Prompt，交给 Qwen API 生成最终回答。管理员界面可以查看实体识别、意图识别、知识图谱检索和向量检索结果，方便调试和验证系统效果。

# 简历写法

## 精简版

**医疗领域 Hybrid RAG 智能问答系统**  
基于 Streamlit、Neo4j、Qdrant、BERT/RoBERTa 和 Qwen API 构建医疗问答系统，实现医疗实体识别、意图识别、知识图谱检索、向量文档检索和证据增强生成。系统支持疾病、药品、症状等结构化关系查询，并扩展 PDF/TXT 医学文档导入与语义检索能力，通过 Graph RAG + Vector RAG 融合降低大模型幻觉。

## 详细版

**医疗领域 Hybrid RAG 智能问答系统 | Python, Streamlit, Neo4j, Qdrant, BERT, Qwen API**

- 构建基于 Streamlit 的医疗问答系统，支持用户登录注册、管理员调试视图、多轮对话窗口和医学知识库检索结果展示。
- 使用 BERT/RoBERTa + BiLSTM 实现医疗实体识别，结合 Aho-Corasick 规则匹配和 TF-IDF 实体对齐，识别疾病、药品、症状、检查项目等实体。
- 基于 Neo4j 构建医疗知识图谱，抽取疾病、药品、食物、检查项目、科室、症状、治疗方法等实体及关系，实现结构化医学知识查询。
- 设计 Prompt-based 意图识别流程，调用 Qwen OpenAI 兼容 API 识别用户问题中的多类别查询意图，降低人工标注意图数据成本。
- 新增 Qdrant 向量检索模块，支持医学 PDF/TXT 文档导入、chunk 切分、sentence-transformers embedding 生成和 top-k 语义检索。
- 实现 Neo4j Graph RAG 与 Qdrant Vector RAG 融合，将结构化图谱结果和非结构化文档片段共同注入 Prompt，提升回答依据覆盖率并减少模型幻觉。
- 将原本依赖本地 Ollama 的大模型调用改造为 Qwen API 调用，降低本地部署硬件门槛，提升项目复现和演示便利性。

## 更偏工程落地的版本

**医疗 KG-RAG 问答系统**

- 负责医疗问答系统的 RAG 流程设计与实现，整合 Streamlit 前端、Neo4j 知识图谱、Qdrant 向量库和 Qwen API，完成从用户问题理解到证据检索再到答案生成的闭环。
- 基于医疗实体词典构建 Aho-Corasick 自动机生成 BIO 标注数据，并使用 RoBERTa-BiLSTM 模型完成疾病、药品、症状等实体识别。
- 设计多意图识别 Prompt，将用户问题映射到疾病简介、病因、治疗方法、用药、检查项目等意图，并据此生成 Neo4j Cypher 查询。
- 扩展非结构化医学文档检索能力，支持 PDF/TXT 文档导入 Qdrant，通过 sentence-transformers 生成向量并进行语义召回。
- 在最终回答阶段融合图谱检索结果与向量检索片段，通过证据增强 Prompt 约束大模型回答，提升医疗问答的可靠性和可解释性。

## 面试时可以强调的关键词

```text
Hybrid RAG
Graph RAG
Vector RAG
Neo4j
Qdrant
sentence-transformers
BERT/RoBERTa-BiLSTM
Aho-Corasick
TF-IDF 实体对齐
Prompt-based Intent Recognition
Evidence-grounded Generation
Streamlit
Qwen API
```
