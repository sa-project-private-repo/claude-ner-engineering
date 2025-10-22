"""
단어 뜻 풀이 생성 모듈
신조어의 의미를 자동으로 생성하는 기능
"""

import os
import re
from typing import List, Dict, Optional
import boto3
import json
from collections import Counter


class DefinitionGenerator:
    """
    신조어 뜻 풀이 자동 생성기

    다음 방법을 지원합니다:
    1. 문맥 기반 추론 (기본)
    2. 형태소 분석 기반
    3. LLM API 기반 (선택사항)
    """

    def __init__(self, use_llm: bool = False, llm_model: str = "claude-3-haiku"):
        """
        Args:
            use_llm: LLM API 사용 여부
            llm_model: 사용할 LLM 모델
        """
        self.use_llm = use_llm
        self.llm_model = llm_model

        if use_llm:
            # Bedrock 클라이언트 초기화
            self.bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

    def generate_definition_from_context(self, word: str, examples: List[str]) -> str:
        """
        문맥 예시로부터 뜻 추론

        Args:
            word: 신조어
            examples: 사용 예시 리스트

        Returns:
            추론된 뜻 풀이
        """
        if not examples:
            return self._generate_definition_from_morphology(word)

        # 문맥 패턴 분석
        patterns = []

        # 공통 동사/형용사 패턴 찾기
        verbs = []
        adjectives = []

        for example in examples:
            # 간단한 패턴 매칭
            if '하다' in example or '되다' in example:
                # 동사형
                patterns.append('동작/상태')
            if '좋다' in example or '싫다' in example or '나쁘다' in example:
                # 감정/평가
                patterns.append('감정/평가')

        # 뜻 생성
        definition = self._infer_meaning_from_patterns(word, examples, patterns)

        return definition

    def _infer_meaning_from_patterns(self, word: str, examples: List[str], patterns: List[str]) -> str:
        """패턴으로부터 의미 추론"""

        # 기본 템플릿
        definition_parts = []

        # 1. 단어 유형 판단
        word_type = self._classify_word_type(word)
        definition_parts.append(word_type)

        # 2. 문맥에서 키워드 추출
        keywords = self._extract_keywords_from_examples(examples)

        # 3. 의미 조합
        if keywords:
            meaning = f"{word_type} {', '.join(keywords[:3])}와(과) 관련된 의미로 사용됨"
        else:
            meaning = f"{word_type} 최근 유행하는 신조어"

        return meaning

    def _classify_word_type(self, word: str) -> str:
        """단어 유형 분류"""

        # 자음만 있는 경우
        if re.match(r'^[ㄱ-ㅎ]+$', word):
            return "[축약어]"

        # 영어 포함
        if re.search(r'[a-zA-Z]', word):
            return "[합성어]"

        # 길이 기반
        if len(word) == 2:
            return "[신조어]"
        elif len(word) >= 4:
            return "[합성 신조어]"

        return "[신조어]"

    def _extract_keywords_from_examples(self, examples: List[str]) -> List[str]:
        """예시에서 키워드 추출"""

        # 간단한 명사 추출 (추후 형태소 분석기로 개선 가능)
        keywords = []

        common_words = {'이', '가', '을', '를', '은', '는', '의', '에', '에서',
                       '하다', '되다', '있다', '없다', '같다', '이다',
                       '완전', '진짜', '너무', '정말', '좀', '아주'}

        for example in examples:
            words = example.split()
            for w in words:
                # 한글만
                clean_word = re.sub(r'[^가-힣]', '', w)
                if clean_word and len(clean_word) >= 2 and clean_word not in common_words:
                    keywords.append(clean_word)

        # 빈도순
        keyword_freq = Counter(keywords)
        return [k for k, v in keyword_freq.most_common(5)]

    def _generate_definition_from_morphology(self, word: str) -> str:
        """형태소 분석 기반 뜻 생성"""

        # 간단한 규칙 기반
        definition_map = {
            r'.*생$': '삶, 생활과 관련된 신조어',
            r'^갓.*': '최고, 최상급을 의미하는 신조어',
            r'.*추$': '추천의 줄임말',
            r'.*루팡$': '쉽게 보상을 받는 상황을 의미',
            r'ㅇㅈ': '인정의 줄임말',
            r'ㄱㅅ': '감사의 줄임말',
            r'ㅋㅋ': '웃음을 나타내는 표현',
        }

        for pattern, meaning in definition_map.items():
            if re.match(pattern, word):
                return meaning

        return "최근 유행하는 신조어"

    def generate_definition_with_llm(self, word: str, examples: List[str],
                                    frequency: int, cohesion: float) -> str:
        """
        LLM API를 사용한 뜻 풀이 생성

        Args:
            word: 신조어
            examples: 사용 예시
            frequency: 출현 빈도
            cohesion: 응집도

        Returns:
            LLM이 생성한 뜻 풀이
        """
        if not self.use_llm:
            return self.generate_definition_from_context(word, examples)

        # 프롬프트 생성
        examples_text = "\n".join([f"- {ex}" for ex in examples[:5]])

        prompt = f"""다음 신조어의 뜻을 한 줄로 간결하게 설명해주세요.

신조어: {word}
출현 빈도: {frequency}회
사용 예시:
{examples_text}

뜻 풀이 (30자 이내로 간결하게):"""

        try:
            # Bedrock Claude API 호출
            response = self.bedrock.invoke_model(
                modelId=self.llm_model,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 100,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                })
            )

            response_body = json.loads(response['body'].read())
            definition = response_body['content'][0]['text'].strip()

            return definition

        except Exception as e:
            print(f"LLM API 호출 실패 ({word}): {e}")
            # 폴백: 문맥 기반 생성
            return self.generate_definition_from_context(word, examples)

    def generate_definitions_batch(self, neologisms: Dict[str, Dict],
                                   use_llm: bool = False) -> Dict[str, Dict]:
        """
        여러 신조어의 뜻을 일괄 생성

        Args:
            neologisms: 신조어 사전
            use_llm: LLM 사용 여부

        Returns:
            뜻 풀이가 추가된 신조어 사전
        """
        print(f"\n=== 뜻 풀이 생성 시작 ===")
        print(f"대상 단어: {len(neologisms)}개")
        print(f"LLM 사용: {use_llm}")

        for word, data in neologisms.items():
            examples = data.get('examples', [])
            frequency = data.get('count', 0)
            cohesion = data.get('cohesion', 0)

            if use_llm and self.use_llm:
                definition = self.generate_definition_with_llm(
                    word, examples, frequency, cohesion
                )
            else:
                definition = self.generate_definition_from_context(word, examples)

            data['definition'] = definition
            print(f"  {word}: {definition}")

        print(f"✓ 뜻 풀이 생성 완료")

        return neologisms

    def create_semantic_dictionary(self, neologisms: Dict[str, Dict]) -> Dict:
        """
        의미 사전 생성 (단어 + 뜻 풀이)

        Args:
            neologisms: 신조어 데이터

        Returns:
            의미 사전
        """
        semantic_dict = {
            'title': '신조어 의미 사전',
            'created_at': json.dumps({"datetime": "now"}, default=str),
            'total_entries': len(neologisms),
            'entries': []
        }

        for word, data in neologisms.items():
            entry = {
                'word': word,
                'definition': data.get('definition', '의미 미정'),
                'type': data.get('type', 'unknown'),
                'frequency': data.get('count', 0),
                'examples': data.get('examples', [])[:3],
                'related_words': self._find_related_words(word, neologisms)
            }
            semantic_dict['entries'].append(entry)

        # 가나다순 정렬
        semantic_dict['entries'].sort(key=lambda x: x['word'])

        return semantic_dict

    def _find_related_words(self, word: str, all_words: Dict[str, Dict],
                           max_related: int = 3) -> List[str]:
        """유사/관련 단어 찾기"""

        related = []

        # 간단한 규칙: 공통 문자가 있는 단어
        for other_word in all_words.keys():
            if other_word == word:
                continue

            # 공통 부분 찾기
            common_chars = set(word) & set(other_word)
            if len(common_chars) >= 2:
                related.append(other_word)

            if len(related) >= max_related:
                break

        return related


# 헬퍼 함수
def add_definitions_to_dictionary(dictionary: Dict, use_llm: bool = False) -> Dict:
    """
    기존 사전에 뜻 풀이 추가

    Args:
        dictionary: 신조어 사전
        use_llm: LLM 사용 여부

    Returns:
        뜻 풀이가 추가된 사전
    """
    generator = DefinitionGenerator(use_llm=use_llm)

    # 단어별로 뜻 생성
    for entry in dictionary.get('words', []):
        word = entry['word']
        examples = entry.get('examples', [])
        frequency = entry.get('frequency', 0)
        cohesion = entry.get('cohesion', 0)

        if use_llm:
            definition = generator.generate_definition_with_llm(
                word, examples, frequency, cohesion
            )
        else:
            definition = generator.generate_definition_from_context(word, examples)

        entry['definition'] = definition

    return dictionary
