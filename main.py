import os
import httpx
from dotenv import load_dotenv
from typing import List
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.output_parsers import JsonOutputParser

load_dotenv()
backend_url = os.getenv("backend_url")
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", temperature=0.7)
app = FastAPI(title="Dynamic Multi-Agent AI Server")

class AgentRequest(BaseModel):
    topic_question: str
    agent_count: int

class AgentRole(BaseModel):
    role_name: str
    description: str

class BackendUpdate(BaseModel):
    agent_name: str
    content: str
    is_final: bool = False

class AgentOrchestrator:
    def __init__(self, request: AgentRequest):
        self.request = request
        self.backend_url = backend_url

    async def _send_to_backend(self, data: BackendUpdate):
        """백엔드 서버로 데이터를 전송하는 유틸리티 함수"""
        print(f"[Backend 전송] {data.agent_name}의 답변 전송 중...")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.backend_url, 
                    json=data.model_dump(),
                    timeout=10.0
                )
                
                response.raise_for_status()
                print(f"[Backend 전송 성공] {data.agent_name}")
                
        except httpx.HTTPStatusError as e:
            print(f"[Backend 응답 에러] 상태 코드: {e.response.status_code}")
        except httpx.RequestError as e:
            print(f"[Backend 연결 실패] 서버가 꺼져 있거나 주소가 틀렸을 수 있습니다: {e}")
        except Exception as e:
            print(f"[기타 전송 에러] {e}")

    async def generate_roles(self) -> List[AgentRole]:
        """질문에 맞는 N개의 에이전트 역할을 생성"""
        parser = JsonOutputParser(pydantic_object=AgentRole)
        
        messages = [
            SystemMessage(content="당신은 전문적인 AI 팀 빌더입니다. 반드시 JSON 리스트 형식으로만 응답하세요."),
            HumanMessage(content=(
                f"질문: '{self.request.topic_question}'\n"
                f"위 질문을 해결하기 위한 서로 다른 전문가 {self.request.agent_count}명을 구성하세요.\n"
                "응답 형식 예시: [{\"role_name\": \"이름\", \"description\": \"설명\"}]"
            ))
        ]

        response = await llm.ainvoke(messages)

        try:
            raw_roles = parser.parse(response.content)
            
            if isinstance(raw_roles, dict):
                raw_roles = [raw_roles]
                
            return [AgentRole(**r) for r in raw_roles]
            
        except Exception as e:
            print(f"JSON 파싱 에러: {e}\n원본 내용: {response.content}")
            # 파싱 실패 시 기본 역할 부여
            return [AgentRole(role_name="일반 전문가", description="분석 및 답변 수행")]

    async def summarize_content(self, current_summary: str, new_content: str) -> str:
        """핵심 키워드와 함께 내용을 3문장 이내로 압축 요약"""
        
        messages = [
            SystemMessage(content=(
                "당신은 기술 전문가들을 위한 정보 요약가입니다.\n"
                "**작성 지침:**\n"
                "1. 마크다운 기호(##, **, *)를 절대 사용하지 마세요.\n"
                "2. 반드시 '핵심 키워드:' 섹션을 먼저 작성하고, 그 아래에 요약 내용을 작성하세요.\n"
                "3. 요약은 이전 전문가 답변에서 새롭게 등장한 중요 개념 위주로 3문장 이내로 작성하세요.\n"
                "4. 모든 답변은 텍스트로만 구성된 평문(Plain Text)이어야 합니다."
            )),
            HumanMessage(content=f"기존 맥락: {current_summary}\n새로운 전문가 답변: {new_content}\n\n위 내용을 요약하세요.")
        ]
        response = await llm.ainvoke(messages)
        summary = response.content.strip()
        
        print(f"[요약 완료]: {summary}\n")

        return summary
    
    async def run_workflow(self):
        """전체 순차 워크플로우 실행"""
        print(f"에이전트 팀 구성 중... (목표: {self.request.agent_count}명)")
        roles = await self.generate_roles()
        print(f"구성 완료: {[role.role_name for role in roles]}")
        
        current_context = "시작 단계입니다."
        final_result = ""

        for i, role in enumerate(roles):
            print(f"[{i+1}/{len(roles)}] {role.role_name} 가동 중...")
            
            # 에이전트 호출 메시지 구조
            agent_messages = [
                SystemMessage(content=(
                    f"당신은 {role.role_name}입니다. {role.description}\n"
                    "**중요 지침:**\n"
                    "1. 마크다운 기호(##, ###, **, *, - 등)를 절대 사용하지 마세요.\n"
                    "2. 가독성을 위해 단락 구분은 오직 줄바꿈(Enter)으로만 하세요.\n"
                    "3. 텍스트로만 구성된 평문(Plain Text) 형식으로 답변하세요.\n"
                    "4. 답변은 반드시 5문장 이내로 핵심만 간결하게 작성하세요."
                )),
                HumanMessage(content=f"요약: {current_context}\n질문: {self.request.topic_question}\n전문적인 의견을 작성하세요.")
            ]
            response = await llm.ainvoke(agent_messages)
            answer = response.content
            
            # 길이 제약 조건을 위반했을 경우 재요약 요청
            retry_count = 0
            max_retries = 3
            while len(answer) > 400 and retry_count < max_retries:
                retry_count += 1
                print(f"[{role.role_name}] 답변 길이 초과로 재요약 수행 ({retry_count}/{max_retries})...")
                retry_messages = agent_messages + [
                    AIMessage(content=answer),
                    HumanMessage(content="답변이 너무 깁니다. 반드시 5문장 이내로 다시 요약해주세요.")
                ]
                response = await llm.ainvoke(retry_messages)
                answer = response.content
            
            # 백엔드에 현재 답변 전송
            is_final = (i == len(roles) - 1)
            print(f"{role.role_name}의 답변: {answer}")
            await self._send_to_backend(BackendUpdate(
                agent_name=role.role_name,
                content=answer,
                is_final=is_final
            ))
            
            # 다음 단계를 위한 요약 업데이트
            if not is_final:
                current_context = await self.summarize_content(current_context, answer)
            else:
                final_result = answer
                print(f"최종 결과: {final_result}")

        return {"status": "success", "result": final_result}
    
@app.post("/run-agents")
async def start_agents(request: AgentRequest):
    if request.agent_count < 1:
        raise HTTPException(status_code=400, detail="에이전트는 최소 1명 이상이어야 합니다.")

    orchestrator = AgentOrchestrator(request)
    try:
        result = await orchestrator.run_workflow()
        return result
    except Exception as e:
        print(f"서버 내부 에러: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

# TODO: 백엔드에 보내는 agent 응답 요약