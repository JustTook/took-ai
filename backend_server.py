from flask import Flask, request

app = Flask(__name__)

@app.route('/agent-output', methods=['POST'])
def receive_agent_output():
    data = request.json
    print("Received agent output:")
    print(f"Agent: {data['agent']}")        # 사용한 agent 이름
    print(f"Task: {data['task']}")          # task 이름 (또는 output.description)
    print(f"Result: {data['output']}")     # task 결과 (원시 출력)

    return '', 200

if __name__ == '__main__':
    app.run(port=8000)