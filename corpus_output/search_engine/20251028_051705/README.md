# 검색 엔진 설정 파일

생성 일시: 2025-10-28T05:17:05.603284
총 단어 수: 26
동의어 그룹: 1

## 파일 목록

1. **synonyms.txt** - Solr 형식 동의어 파일
   - OpenSearch/Elasticsearch synonym filter용
   - 형식: word1, word2, word3

2. **synonyms_wordnet.txt** - WordNet 형식 동의어 파일
   - 형식: word1 => word2, word3

3. **user_dictionary.txt** - 기본 사용자 사전
   - 한 줄에 하나씩 단어 나열

4. **nori_user_dictionary.txt** - Nori Tokenizer용 사용자 사전
   - 품사 태그 포함
   - 형식: word POS_TAG

5. **index_settings.json** - OpenSearch/Elasticsearch 인덱스 설정
   - analyzer, tokenizer, filter 설정 포함

## 사용 방법

### 1. 파일 다운로드
```bash
aws s3 cp s3://neologismgluestack-neologismdatabucket964d4a93-x7prphtbefoc/output/corpus/search_engine/20251028_051705/ . --recursive
```

### 2. OpenSearch/Elasticsearch config 디렉토리에 복사
```bash
cp synonyms.txt $OPENSEARCH_HOME/config/analysis/
cp nori_user_dictionary.txt $OPENSEARCH_HOME/config/
```

### 3. 인덱스 생성
```bash
curl -X PUT "localhost:9200/neologism_search" \
  -H 'Content-Type: application/json' \
  -d @index_settings.json
```

### 4. OpenSearch/Elasticsearch 재시작
```bash
sudo systemctl restart opensearch
```

## 주의사항

- 동의어/사용자 사전 파일을 변경한 후에는 인덱스를 재생성하거나 reload API를 사용해야 합니다.
- synonym filter의 `updateable: true` 설정으로 runtime 업데이트 가능

## 참고

- Nori Tokenizer: https://www.elastic.co/guide/en/elasticsearch/plugins/current/analysis-nori.html
- Synonym Token Filter: https://opensearch.org/docs/latest/analyzers/token-filters/synonym/
