import os
import httpx
from datetime import datetime
from dotenv import load_dotenv
from typing import List, Optional
from pydantic import BaseModel, field_validator
from fastapi import FastAPI, HTTPException
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.output_parsers import JsonOutputParser

load_dotenv()
BACKEND_URL = os.getenv("BACKEND_URL")
if not BACKEND_URL:
    print("경고: .env 파일에 'BACKEND_URL'이 설정되지 않았습니다.")

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.7)
app = FastAPI(title="Dynamic Multi-Agent AI Server")

# 프롬프트 템플릿 정의
PROMPT_TEAM_BUILDER_SYSTEM = "당신은 전문적인 AI 팀 빌더입니다. 반드시 JSON 리스트 형식으로만 응답하세요."
PROMPT_TEAM_BUILDER_USER_TEMPLATE = (
    "질문: '{topic_question}'\n"
    "위 질문을 해결하기 위한 서로 다른 전문가 {agent_count}명을 구성하세요.\n"
    "각 전문가에게는 역할에 어울리는 친근한 이름(예: John, James, Jenny, Emily 등)을 부여하세요.\n"
    "응답 형식 예시: [{{ \"name\": \"이름\", \"role\": \"직업\", \"prompt\": \"설명\" }}]"
)

PROMPT_SUMMARY_SYSTEM = (
    "당신은 기술 전문가들을 위한 정보 요약가입니다.\n"
    "**작성 지침:**\n"
    "1. 마크다운 기호(##, **, *)를 절대 사용하지 마세요.\n"
    "2. 반드시 '핵심 키워드:' 섹션을 먼저 작성하고, 그 아래에 요약 내용을 작성하세요.\n"
    "3. 요약은 이전 전문가 답변에서 새롭게 등장한 중요 개념 위주로 3문장 이내로 작성하세요.\n"
    "4. 모든 답변은 텍스트로만 구성된 평문(Plain Text)이어야 합니다."
)
PROMPT_SUMMARY_USER_TEMPLATE = "기존 맥락: {current_summary}\n새로운 전문가 답변: {new_content}\n\n위 내용을 요약하세요."

PROMPT_AGENT_SYSTEM_TEMPLATE = (
    "당신은 {name}입니다. {prompt}\n"
    "**중요 지침:**\n"
    "1. 마크다운 기호(##, ###, **, *, - 등)를 절대 사용하지 마세요.\n"
    "2. 가독성을 위해 단락 구분은 오직 줄바꿈(Enter)으로만 하세요.\n"
    "3. 텍스트로만 구성된 평문(Plain Text) 형식으로 답변하세요.\n"
    "4. 답변은 반드시 5문장 이내로 핵심만 간결하게 작성하세요."
)
PROMPT_AGENT_USER_TEMPLATE = "요약: {context}\n질문: {question}\n전문적인 의견을 작성하세요."

PROMPT_RETRY_LENGTH = "답변이 너무 깁니다. 반드시 5문장 이내로 다시 요약해주세요."

PROMPT_FINAL_SUMMARY_SYSTEM = (
    "당신은 전체 토론 내용을 종합하여 최종 결론을 내리는 진행자입니다.\n"
    "**작성 지침:**\n"
    "1. 전체 전문가들의 의견을 종합하여 7줄 내외로 요약하세요.\n"
    "2. 마크다운 없이 평문(Plain Text)으로 작성하세요."
)
PROMPT_FINAL_SUMMARY_USER_TEMPLATE = (
    "질문: {question}\n\n"
    "전문가 답변 모음:\n{all_answers}\n\n"
    "위 내용을 바탕으로 최종 요약을 작성하세요."
)

class AgentInfo(BaseModel):
    name: str
    role: str
    prompt: str

class AgentRequest(BaseModel):
    topic_id: str
    topic_question: str
    agent_auto: bool
    agent_info: List[AgentInfo] = []
    topic_summary: Optional[str] = None

class AgentReplyRequest(BaseModel):
    topic_id: str
    topic_question: str
    topic_summary: str
    agent_info: List[AgentInfo]

    @field_validator('topic_summary')
    @classmethod
    def check_summary_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('이전 대화 요약(topic_summary)은 필수입니다.')
        return v

class BackendUpdate(BaseModel):
    topic_id: str
    name: str
    role: str
    contents: str
    timestamp: str
    is_final: bool

class AgentOrchestrator:
    def __init__(self, request: AgentRequest):
        self.request = request
        self.backend_url = BACKEND_URL
        if self.request.agent_auto:
            self.agent_count = 3
        else:
            self.agent_count = len(self.request.agent_info)

    async def _send_to_backend(self, data: BackendUpdate):
        """백엔드 서버로 데이터를 전송하는 유틸리티 함수"""

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.backend_url, 
                    json=data.model_dump(),
                    timeout=10.0
                )
                
                response.raise_for_status()
                
        except httpx.HTTPStatusError as e:
            print(f"[Backend 응답 에러] 상태 코드: {e.response.status_code}")
        except httpx.RequestError as e:
            print(f"[Backend 연결 실패] 서버가 꺼져 있거나 주소가 틀렸을 수 있습니다: {e}")
        except Exception as e:
            print(f"[기타 전송 에러] {e}")

    async def generate_roles(self) -> List[AgentInfo]:
        """질문에 맞는 N개의 에이전트 역할을 생성"""

        parser = JsonOutputParser(pydantic_object=AgentInfo)
        
        messages = [
            SystemMessage(content=PROMPT_TEAM_BUILDER_SYSTEM),
            HumanMessage(content=PROMPT_TEAM_BUILDER_USER_TEMPLATE.format(
                topic_question=self.request.topic_question,
                agent_count=self.agent_count
            ))
        ]

        response = await llm.ainvoke(messages)

        try:
            raw_roles = parser.parse(response.content)
            
            if isinstance(raw_roles, dict):
                raw_roles = [raw_roles]
                
            return [AgentInfo(**r) for r in raw_roles]
            
        except Exception as e:
            print(f"JSON 파싱 에러: {e}\n원본 내용: {response.content}")
            # 파싱 실패 시 기본 역할 부여
            return [AgentInfo(name="일반 전문가", role="Generalist", prompt="분석 및 답변 수행")]

    async def summarize_content(self, current_summary: str, new_content: str) -> str:
        """핵심 키워드와 함께 내용을 3문장 이내로 압축 요약"""
        
        messages = [
            SystemMessage(content=PROMPT_SUMMARY_SYSTEM),
            HumanMessage(content=PROMPT_SUMMARY_USER_TEMPLATE.format(
                current_summary=current_summary,
                new_content=new_content
            ))
        ]
        response = await llm.ainvoke(messages)
        summary = response.content.strip()

        return summary
    
    async def generate_final_summary(self, all_answers: str) -> str:
        """모든 답변을 종합하여 최종 요약 생성"""

        messages = [
            SystemMessage(content=PROMPT_FINAL_SUMMARY_SYSTEM),
            HumanMessage(content=PROMPT_FINAL_SUMMARY_USER_TEMPLATE.format(
                question=self.request.topic_question,
                all_answers=all_answers
            ))
        ]
        response = await llm.ainvoke(messages)
        return response.content.strip()

    async def run_workflow(self):
        """전체 순차 워크플로우 실행"""
        
        if self.request.agent_auto:
            roles = await self.generate_roles()
        else:
            roles = self.request.agent_info
            
        if self.request.topic_summary:
            current_context = f"이전 대화 요약: {self.request.topic_summary}"
        else:
            current_context = "시작 단계입니다."
            
        all_agent_responses = []

        for i, role in enumerate(roles):
            # 에이전트 호출 메시지 구조
            agent_messages = [
                SystemMessage(content=PROMPT_AGENT_SYSTEM_TEMPLATE.format(
                    name=role.name,
                    prompt=role.prompt
                )),
                HumanMessage(content=PROMPT_AGENT_USER_TEMPLATE.format(context=current_context, question=self.request.topic_question))
            ]
            response = await llm.ainvoke(agent_messages)
            answer = response.content
            
            # 길이 제약 조건을 위반했을 경우 재요약 요청
            retry_count = 0
            max_retries = 3
            while len(answer) > 400 and retry_count < max_retries:
                retry_count += 1
                print(f"[{role.name}] 답변 길이 초과로 재요약 수행 ({retry_count}/{max_retries})...")
                retry_messages = agent_messages + [
                    AIMessage(content=answer),
                    HumanMessage(content=PROMPT_RETRY_LENGTH)
                ]
                response = await llm.ainvoke(retry_messages)
                answer = response.content
            
            all_agent_responses.append(f"[{role.name} ({role.role})]: {answer}")
            
            # 백엔드에 현재 답변 전송
            is_final = (i == len(roles) - 1)
            await self._send_to_backend(BackendUpdate(
                topic_id=self.request.topic_id,
                name=role.name,
                role=role.role,
                contents=answer,
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                is_final=False
            ))
            
            # 다음 단계를 위한 요약 업데이트
            if not is_final:
                current_context = await self.summarize_content(current_context, answer)

        # 최종 결론 생성 및 전송
        final_summary = await self.generate_final_summary("\n\n".join(all_agent_responses))
        
        await self._send_to_backend(BackendUpdate(
            topic_id=self.request.topic_id,
            name="최종 결론",
            role="System",
            contents=final_summary,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            is_final=True
        ))
        
        return {"status": "success", "result": final_summary}
    
@app.post("/agent/run/init")
async def start_agents(request: AgentRequest):
    if not request.agent_auto and not request.agent_info:
        raise HTTPException(status_code=400, detail="수동 모드 시 에이전트 정보가 필요합니다.")

    orchestrator = AgentOrchestrator(request)
    try:
        result = await orchestrator.run_workflow()
        return result
    except Exception as e:
        print(f"서버 내부 에러: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/agent/run/reply")
async def continue_agents(request: AgentReplyRequest):
    # AgentReplyRequest를 AgentRequest로 변환 (수동 모드 고정)
    internal_request = AgentRequest(
        topic_id=request.topic_id,
        topic_question=request.topic_question,
        agent_auto=False,
        agent_info=request.agent_info,
        topic_summary=request.topic_summary
    )

    orchestrator = AgentOrchestrator(internal_request)
    try:
        await orchestrator.run_workflow()
        return {"status": "success"}
    except Exception as e:
        print(f"서버 내부 에러: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000)