from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # 解决跨域

@app.post("/api/report")
def api_report():
    
    req_data = request.get_json()
    date = req_data.get("date", "")
    member = req_data.get("member", "")

    # 模拟假原始数据
    raw_info = {
        "date": date,
        "member": member,
        "github": [
            {"repo": "demo-project", "commit": "修复前端样式bug"},
            {"repo": "demo-project", "commit": "完成SDD文档编写"}
        ],
        "lark_msg": [
            "上午：需求评审会议",
            "下午：前后端联调测试"
        ]
    }

    # 模拟生成的日报markdown文本
    md_report = f"""# 个人日报
**日期：{date}**
**汇报人：{member}**

## 今日完成
1. 完成SDD规范文档撰写
2. 前端页面开发与样式调整
3. 后端接口联调测试

## 遇到问题
- 环境依赖包缺失，逐步安装httpx、pyyaml等依赖
- 跨域问题，使用flask-cors解决

## 明日计划
1. 完善项目注释
2. 整理项目复现报告
"""
    return jsonify({
        "code": 0,
        "raw": raw_info,
        "data": md_report
    })

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)