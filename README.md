# blast-guesser Project / blast-guesser 项目

## Overview / 概述
The Blast Guesser project is a web application built using FastAPI that allows users to make manual and automatic guesses for players in a game. The application connects to a game server, processes user inputs, and provides recommendations for the best candidates based on previous guesses.

Blast Guesser 项目是一个使用 FastAPI 构建的 Web 应用程序，允许用户在游戏中进行手动和自动猜测玩家。该应用程序连接到游戏服务器，处理用户输入，并根据之前的猜测提供最佳候选人推荐。

## Features / 功能特性
- **Manual Guessing / 手动猜测**: Users can input their guesses and receive recommendations for the most suitable candidates based on game logic.
  用户可以输入他们的猜测，并根据游戏逻辑获取最适合的候选人推荐。
- **Automatic Guessing / 自动猜测**: The application can automatically suggest guesses based on predefined strategies and player data.
  应用程序可以基于预定义策略和玩家数据自动推荐猜测。
- **Real-time Communication / 实时通信**: Utilizes WebSocket for real-time communication with the game server.
  使用 WebSocket 与游戏服务器进行实时通信。
- **Data Analysis / 数据分析**: Provides entropy-based analysis of player data to optimize guessing strategies.
  提供基于熵的玩家数据分析，优化猜测策略。
- **User-friendly Interface / 用户友好界面**: Simple and intuitive web interface for interacting with the game.
  简单直观的 Web 界面，方便与游戏交互。

## Project Structure / 项目结构
```
blast-guesser
├── app
│   ├── api
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── core
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── game_client.py
│   ├── models
│   │   ├── __init__.py
│   │   └── schemas.py
│   ├── services
│   │   ├── __init__.py
│   │   └── game_service.py
│   ├── static
│   │   ├── css
│   │   │   └── styles.css
│   │   └── js
│   │       └── main.js
│   ├── templates
│   │   ├── base.html
│   │   └── index.html
│   ├── __init__.py
│   └── main.py
├── countries.json
├── players_with_entropy.json
├── requirements.txt
└── README.md
```

## Installation / 安装
To set up the project, clone the repository and install the required dependencies:

要设置项目，请克隆仓库并安装所需的依赖项：

```bash
git clone [<repository-url>](https://github.com/UchihaStesla/friberg.git)
cd blast-guesser
pip install -r requirements.txt
```

## Usage / 使用方法
1. Start the FastAPI application / 启动 FastAPI 应用程序:
   ```bash
   uvicorn app.main:app --reload
   ```
2. Open your browser and navigate to `http://localhost:8000` to access the application.
   
   打开浏览器并导航到 `http://localhost:8000` 来访问应用程序。

## API Endpoints / API 端点
- **POST /manual-guess**: Submit a manual guess and receive recommendations.
  
  提交手动猜测并接收推荐。
  
- **POST /auto-guess**: Trigger automatic guessing based on player data.
  
  根据玩家数据触发自动猜测。

- **GET /recommendations**: Get statistics about past guesses and success rates.
  
  获取选手的推荐信息。

## Technical Details / 技术细节
- **FastAPI Framework**: High-performance web framework for building APIs with Python.
  
  用于使用 Python 构建 API 的高性能 Web 框架。
  
- **WebSocket Communication**: Real-time bidirectional communication with the game server.
  
  与游戏服务器进行实时双向通信。
  
- **Jinja2 Templates**: Server-side rendering of HTML templates.
  
  HTML 模板的服务器端渲染。
  
- **Entropy-based Algorithm**: Uses information theory to calculate the optimal next guess.
  
  使用信息论计算最佳的下一个猜测。

## Development / 开发
To contribute to the development:

参与开发：

1. Set up a virtual environment / 设置虚拟环境:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install development dependencies / 安装开发依赖:
   ```bash
   pip install -r requirements.txt
   ```


## Contributing / 贡献
Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

欢迎贡献！请为任何增强功能或错误修复打开问题或提交拉取请求。

## License / 许可
This project is licensed under the MIT License. See the LICENSE file for more details.

该项目基于 MIT 许可证。有关更多详细信息，请参阅 LICENSE 文件。