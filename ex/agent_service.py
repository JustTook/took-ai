import os
import inspect
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
import tools 

# API 키 설정
os.environ["GOOGLE_API_KEY"] = "AIzaSyBwOa51LE5f7K7NmbT9PtbEeFG0ddV8WYk" 

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite", 
    temperature=0
)

# 2. 도구 로딩
my_tools_list = [
    obj for name, obj in inspect.getmembers(tools) 
    if isinstance(obj, BaseTool)
]
tool_map = {t.name: t for t in my_tools_list}

llm_with_tools = llm.bind_tools(my_tools_list)

def run_agent(query):
    system_instruction = """
    당신은 '전문가 팀을 조율하는 매니저'입니다.
    사용자가 취업, 조언, 정보, 날씨 등을 물어보면 **절대 직접 대답하지 마세요.**
    반드시 제공된 도구(Tool) 중 가장 적절한 것을 선택해서 실행해야 합니다.
    특히 '방법', '조언', '계획' 같은 질문에는 무조건 'consult_experts_team' 도구를 사용하세요.
    """

    try:
        ai_msg = llm_with_tools.invoke([
            SystemMessage(content=system_instruction),
            HumanMessage(content=query)
        ])
        
        if ai_msg.tool_calls:
            tool_call = ai_msg.tool_calls[0]
            tool_name = tool_call['name']
            tool_args = tool_call['args']
            
            print(f" 판단: '{tool_name}' 도구를 사용합니다.")
            
            selected_tool = tool_map.get(tool_name)
            if selected_tool:
                result = selected_tool.invoke(tool_args)
                print(f"\n✅ [결과]\n{result}\n")
            else:
                print("도구를 찾을 수 없습니다.")
        else:
            # 그래도 말을 안 들으면 혼내는 메시지 출력 (디버깅용)
            print(f"\n🗣️ [AI가 도구를 안 썼음 - 경고 필요]\n{ai_msg.content}\n")
            
    except Exception as e:
        print(f"🚨 에러 발생: {e}")

# --- 메인 루프 ---
if __name__ == "__main__":
    print(f"✅ 시스템 준비 완료")
    print("🤖 질문을 입력하세요 (종료: exit)")
    
    while True:
        user_input = input("\nUser >> ")
        if user_input.lower() in ["exit", "quit"]: break
        if not user_input.strip(): continue
        run_agent(user_input)