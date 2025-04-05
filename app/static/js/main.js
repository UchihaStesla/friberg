document.addEventListener('DOMContentLoaded', function () {
    // 获取DOM元素
    const connectBtn = document.getElementById('connectBtn');
    const disconnectBtn = document.getElementById('disconnectBtn');
    const roomIdInput = document.getElementById('roomId');
    const connectionStatus = document.getElementById('connectionStatus');
    const gamePanel = document.querySelector('.game-panel');
    const autoGuessBtn = document.getElementById('autoGuessBtn');
    const guessCounter = document.getElementById('guessCounter');
    const playerList = document.getElementById('playerList');
    const searchPlayer = document.getElementById('searchPlayer');
    const guessResults = document.getElementById('guessResults');
    const constraints = document.getElementById('constraints');
    const readyBtn = document.getElementById('readyBtn');

    // 状态变量
    let isConnected = false;
    let remainingGuesses = 8;
    let currentRecommendations = [];
    let currentConstraints = {};
    let gameSocket = null;
    let currentRoomId = null;

    // 建立WebSocket连接
    // 在connectWebSocket函数中添加连接状态监控
    function connectWebSocket(roomId) {
        // 如果已存在连接，先关闭
        if (gameSocket && gameSocket.readyState !== WebSocket.CLOSED) {
            gameSocket.close();
        }

        // 构建WebSocket URL
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/ws/${roomId}`;
        console.log(`正在连接WebSocket: ${wsUrl}`);

        // 创建WebSocket连接
        gameSocket = new WebSocket(wsUrl);

        // 连接打开时
        gameSocket.onopen = function (event) {
            console.log("✅ WebSocket连接已建立");

            // 设置心跳检测，每15秒发送一次
            window.wsHeartbeat = setInterval(() => {
                if (gameSocket && gameSocket.readyState === WebSocket.OPEN) {
                    gameSocket.send("ping");
                }
            }, 15000);
        };

        // 接收消息时
        gameSocket.onmessage = function (event) {
            try {
                if (event.data === "pong") {
                    console.log("收到心跳响应");
                    return;
                }

                const data = JSON.parse(event.data);
                console.log("📥 收到WebSocket消息:", data.type, data);
                handleWebSocketMessage(data);
            } catch (error) {
                console.error("❌ 解析WebSocket消息出错:", error);
            }
        };

        // 连接关闭时
        gameSocket.onclose = function (event) {
            console.log(`⚠️ WebSocket连接已关闭 (code: ${event.code}, reason: ${event.reason})`);

            // 清除心跳
            if (window.wsHeartbeat) {
                clearInterval(window.wsHeartbeat);
            }

            // 如果是在游戏中意外关闭且不是正常关闭码，尝试重新连接
            if (isConnected && event.code !== 1000) {
                console.log("🔄 尝试重新连接WebSocket...");
                setTimeout(() => connectWebSocket(roomId), 3000);
            }
        };

        // 连接错误时
        gameSocket.onerror = function (error) {
            console.error("❌ WebSocket错误:", error);
        };
    }
    // 处理WebSocket消息
    function handleWebSocketMessage(data) {
        console.log("处理WebSocket消息:", data.type, data);

        switch (data.type) {
            case "INITIAL_STATE":
            case "STATE_UPDATE":
                // 处理状态更新
                console.log("更新游戏状态:", data);

                // 特别记录胜利次数的变化
                if (data.player_wins !== undefined) {
                    console.log(`胜利次数更新: ${data.player_wins}`);

                    // 如果是0，可能是重置 - 确保UI显示正确
                    if (data.player_wins === 0 && data.game_phase === 'lobby') {
                        console.log("检测到游戏重置 - 清除所有状态");
                        // 这里可以添加额外的UI重置代码
                    }
                }

                updateGameMetadata({
                    best_of: data.best_of,
                    current_wins: data.player_wins,
                    required_wins: data.required_wins,
                    current_phase: data.game_phase,
                    remaining_guesses: data.remaining_guesses
                });
                
                // 当阶段变为game时自动刷新推荐
                if (data.game_phase === 'game') {
                    console.log("游戏阶段变为'game'，刷新推荐列表");
                    loadRecommendations(currentRoomId);

                    // 确保准备按钮处于正确状态
                    readyBtn.disabled = false;
                    readyBtn.textContent = '准备就绪';
                } else if (data.game_phase === 'end' || data.game_phase === 'ready') {
                    // 在游戏结束或准备阶段，确保准备按钮可用
                    readyBtn.disabled = false;
                    readyBtn.textContent = '准备就绪';
                }
                break;

            case "GUESS_RESULT":
                // 处理新猜测结果
                console.log("处理猜测结果:", data);
                addGuessResult({
                    success: data.result.isSuccess,
                    result: data.result,
                    message: data.result.isSuccess ? "猜测成功!" : "猜测结果已更新"
                });

                // 更新剩余猜测次数
                remainingGuesses = data.remaining_guesses;
                guessCounter.textContent = remainingGuesses;

                // 刷新推荐列表
                loadRecommendations(currentRoomId);
                break;

            default:
                console.log("未处理的消息类型:", data.type);
        }
    }

    // 更新updateGameMetadata函数，确保UI正确更新
    function updateGameMetadata(metadata) {
        console.log("更新游戏元数据:", metadata); // 添加调试日志

        // 更新游戏模式显示
        const gamePanel = document.querySelector('.game-panel');
        const gameModeEl = document.getElementById('gameMode') || document.createElement('div');
        gameModeEl.id = 'gameMode';
        gameModeEl.className = 'game-mode-info';

        // 格式化游戏模式文本
        let modeText = '';
        if (metadata.best_of === 'best_of_1') {
            modeText = '单局游戏';
        } else {
            const requiredWins = metadata.required_wins || 2;
            const currentWins = metadata.current_wins || 0;
            modeText = `${metadata.best_of.replace('best_of_', 'BO')} (${currentWins}/${requiredWins}胜)`;
        }

        // 获取当前阶段的显示名称
        const phaseDisplayName = getPhaseDisplayName(metadata.current_phase);

        gameModeEl.innerHTML = `
            <div class="mode-label">游戏模式:</div>
            <div class="mode-value">${modeText}</div>
            <div class="phase-label">当前阶段:</div>
            <div class="phase-value">${phaseDisplayName}</div>
        `;

        // 更新猜测次数（如果有提供）
        if (metadata.remaining_guesses !== undefined) {
            guessCounter.textContent = metadata.remaining_guesses;
            remainingGuesses = metadata.remaining_guesses;
            console.log(`更新剩余猜测次数: ${metadata.remaining_guesses}`);
        }

        // 将元素添加到游戏面板
        if (!document.getElementById('gameMode')) {
            const panelHeader = document.querySelector('.panel-header');
            if (panelHeader) {
                panelHeader.appendChild(gameModeEl);
            }
        }
    }
    // 连接到游戏房间
    connectBtn.addEventListener('click', async function () {
        const roomId = roomIdInput.value.trim();
        if (!roomId) {
            showConnectionStatus('请输入房间ID', 'error');
            return;
        }

        showConnectionStatus('正在连接...', '');

        try {
            const response = await fetch('/api/connect', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ room_id: roomId })
            });

            const data = await response.json();

            if (data.success) {
                isConnected = true;
                currentRoomId = roomId; // 保存当前房间ID
                showConnectionStatus('已连接，请点击准备就绪', 'connected');
                toggleConnectionButtons();
                readyBtn.disabled = false;

                // 建立WebSocket连接
                connectWebSocket(roomId);
            } else {
                showConnectionStatus(`连接失败: ${data.message}`, 'error');
            }
        } catch (error) {
            showConnectionStatus(`连接错误: ${error.message}`, 'error');
        }
    });

    // 断开连接
    disconnectBtn.addEventListener('click', async function () {
        const roomId = roomIdInput.value.trim();

        try {
            const response = await fetch('/api/disconnect', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ room_id: roomId })
            });

            // 添加状态码检查
            if (!response.ok) {
                throw new Error(`HTTP错误: ${response.status}`);
            }

            let data;
            try {
                data = await response.json();
            } catch (jsonError) {
                console.error("JSON解析失败:", jsonError);
                // 即使JSON解析失败，也重置UI状态
                isConnected = false;
                showConnectionStatus('已断开连接', '');
                toggleConnectionButtons();
                hideGamePanel();
                resetGameState();
                return;
            }

            if (data.success) {
                isConnected = false;

                // 关闭WebSocket连接
                if (gameSocket && gameSocket.readyState !== WebSocket.CLOSED) {
                    gameSocket.close();
                    gameSocket = null;
                }

                showConnectionStatus('已断开连接', '');
                toggleConnectionButtons();
                hideGamePanel();
                resetGameState();
                currentRoomId = null; // 清除房间ID
            } else {
                showConnectionStatus(`断开连接失败: ${data.message}`, 'error');
            }
        } catch (error) {
            console.error("断开连接错误:", error);
            showConnectionStatus(`断开连接错误: ${error.message}`, 'error');
            // 在出错的情况下也重置状态，确保UI一致性
            isConnected = false;
            toggleConnectionButtons();
            hideGamePanel();
            resetGameState();
        }
    });

    // 自动猜测
    autoGuessBtn.addEventListener('click', async function () {
        if (!isConnected) return;

        const roomId = roomIdInput.value.trim();
        autoGuessBtn.disabled = true;
        autoGuessBtn.textContent = '猜测中...';

        try {
            const response = await fetch('/api/auto-guess', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ room_id: roomId })
            });

            const data = await response.json();

            if (data.success) {
                addGuessResult({
                    success: true,
                    message: '自动猜测成功',
                    result: data.result
                });

                // 刷新推荐列表
                loadRecommendations(roomId);
            } else {
                addGuessResult({
                    success: false,
                    message: `自动猜测失败: ${data.message}`
                });
            }
        } catch (error) {
            addGuessResult({
                success: false,
                message: `自动猜测错误: ${error.message}`
            });
        } finally {
            autoGuessBtn.disabled = false;
            autoGuessBtn.textContent = '自动猜测';
        }
    });

    // 搜索选手
    searchPlayer.addEventListener('input', function () {
        filterPlayers(this.value.toLowerCase());
    });

    // 添加准备就绪按钮事件处理
    // 修改准备就绪按钮事件处理器
    readyBtn.addEventListener('click', async function () {
        const roomId = roomIdInput.value.trim();
        if (!roomId || !isConnected) return;

        readyBtn.disabled = true;
        readyBtn.textContent = '准备中...';

        try {
            const response = await fetch('/api/player-ready', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ room_id: roomId })
            });

            const data = await response.json();

            if (data.success) {
                showConnectionStatus('已准备就绪，游戏可以开始', 'connected');
                showGamePanel();
                loadRecommendations(roomId);

                // 添加这两行，重新启用准备按钮
                readyBtn.disabled = false;
                readyBtn.textContent = '再次准备';
            } else {
                showConnectionStatus(`准备失败: ${data.message}`, 'error');
                readyBtn.disabled = false;
                readyBtn.textContent = '准备就绪';
            }
        } catch (error) {
            showConnectionStatus(`准备错误: ${error.message}`, 'error');
            readyBtn.disabled = false;
            readyBtn.textContent = '准备就绪';
        }
    });

    // 加载推荐选手
    async function loadRecommendations(roomId) {
        try {
            const response = await fetch('/api/recommendations', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ room_id: roomId })
            });

            const data = await response.json();
            console.log("API返回数据:", data); // 调试输出

            if (data.success) {
                // 确保recommendations是一个数组
                if (Array.isArray(data.recommendations)) {
                    currentRecommendations = data.recommendations;
                    renderPlayerList(currentRecommendations);
                } else {
                    console.error("API返回的推荐数据不是数组:", data.recommendations);
                    playerList.innerHTML = `<div class="error-message">推荐数据格式错误</div>`;
                    return;
                }

                // 处理游戏元数据
                if (data.game_metadata) {
                    updateGameMetadata(data.game_metadata);
                }

                // 处理约束条件
                if (data.constraints) {
                    updateConstraintsDisplay(data.constraints);
                }
            } else {
                playerList.innerHTML = `<div class="error-message">加载推荐失败: ${data.message}</div>`;
            }
        } catch (error) {
            console.error("加载推荐错误:", error);
            playerList.innerHTML = `<div class="error-message">加载推荐错误: ${error.message}</div>`;
        }
    }

    // 发送手动猜测
    // 修改sendManualGuess函数，移除本地减少计数的调用
    async function sendManualGuess(playerId) {
        if (!isConnected) return;

        const roomId = roomIdInput.value.trim();

        try {
            const response = await fetch('/api/manual-guess', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ room_id: roomId, player_id: playerId })
            });

            const data = await response.json();

            // 移除这一行，使用WebSocket更新替代
            // decrementGuessCounter();

            addGuessResult(data);

            // 如果猜测成功，显示成功消息并刷新列表
            if (data.success) {
                // 检查是否游戏结束
                if (data.result && data.result.isSuccess) {
                    showSuccessMessage(data.result);
                }

                // 刷新推荐列表
                loadRecommendations(roomId);
            }
        } catch (error) {
            addGuessResult({
                success: false,
                message: `猜测错误: ${error.message}`
            });
        }
    }

    // 渲染选手列表
    function renderPlayerList(players) {
        playerList.innerHTML = '';

        if (!players || players.length === 0) {
            playerList.innerHTML = '<div class="empty-message">没有可推荐的选手</div>';
            return;
        }

        players.forEach(player => {
            const playerCard = document.createElement('div');
            playerCard.className = 'player-card';
            playerCard.dataset.playerId = player.player_id;

            const imageUrl = player.image_url || 'https://via.placeholder.com/150?text=No+Image';

            // 处理团队显示
            let teamDisplay = '无团队';
            if (player.team) {
                if (typeof player.team === 'object' && player.team !== null) {
                    teamDisplay = player.team.name || '未知团队';
                } else {
                    teamDisplay = player.team;
                }
            }

            playerCard.innerHTML = `
                <img src="${imageUrl}" alt="${player.nickname || '未知选手'}">
                <div class="player-name">${player.nickname || '未知选手'}</div>
                <div class="player-info">
                    ${player.first_name || ''} ${player.last_name || ''}<br>
                    ${player.nationality || '未知国籍'} | ${teamDisplay}<br>
                    ${player.role || '未知角色'} | ${player.age ? player.age + '岁' : '未知年龄'}
                </div>
                <div class="player-entropy">熵值: ${player.entropy_value ? player.entropy_value.toFixed(3) : 'N/A'}</div>
            `;

            playerCard.addEventListener('click', function () {
                const playerId = this.dataset.playerId;
                if (playerId) {
                    sendManualGuess(playerId);
                }
            });

            playerList.appendChild(playerCard);
        });
    }

    // 过滤选手列表
    function filterPlayers(searchText) {
        if (!currentRecommendations) return;

        const filteredPlayers = currentRecommendations.filter(player => {
            const fullName = `${player.first_name || ''} ${player.last_name || ''} ${player.nickname || ''}`.toLowerCase();
            const nationality = player.nationality ? player.nationality.toLowerCase() : '';
            const team = player.team ? player.team.toLowerCase() : '';
            const role = player.role ? player.role.toLowerCase() : '';

            return fullName.includes(searchText) ||
                nationality.includes(searchText) ||
                team.includes(searchText) ||
                role.includes(searchText);
        });

        renderPlayerList(filteredPlayers);
    }

    // 添加猜测结果
    function addGuessResult(data) {
        const resultElement = document.createElement('div');
        resultElement.className = 'guess-result';

        if (data.success && data.result) {
            const result = data.result;
            const isSuccess = result.isSuccess;

            resultElement.innerHTML = `
                <div class="result-header">
                    <div class="result-player">${result.firstName || ''} ${result.lastName || ''} (${result.nickname || '未知'})</div>
                    <div class="result-status ${isSuccess ? 'status-correct' : 'status-incorrect'}">
                        ${isSuccess ? '正确' : '错误'}
                    </div>
                </div>
                <div class="result-details">
                    ${renderResultDetails(result)}
                </div>
            `;
        } else {
            resultElement.innerHTML = `
                <div class="result-message">${data.message || '猜测失败'}</div>
            `;
        }

        guessResults.insertBefore(resultElement, guessResults.firstChild);
    }

    // 渲染猜测结果详情
    function renderResultDetails(result) {
        let detailsHtml = '';

        // 国籍 部分保持不变...

        // 团队 - 修改这部分
        if (result.team) {
            const teamResult = result.team.result;
            // 正确处理团队数据
            let teamValue = '';
            if (result.team.data) {
                if (typeof result.team.data === 'object' && result.team.data !== null) {
                    teamValue = result.team.data.name || '未知团队';
                } else {
                    teamValue = result.team.data || '未知团队';
                }
            } else {
                teamValue = '无团队';
            }

            let iconClass = teamResult === 'CORRECT' ? 'icon-correct' : 'icon-wrong';

            detailsHtml += `
                <div class="result-item">
                    <span class="${iconClass}">●</span>
                    <span>团队: ${teamValue}</span>
                </div>
            `;
        }

        // 年龄
        if (result.age) {
            const ageResult = result.age.result;
            const ageValue = result.age.value || 0;
            let iconClass = 'icon-wrong';
            let direction = '';

            if (ageResult === 'CORRECT') {
                iconClass = 'icon-correct';
            } else if (ageResult.includes('CLOSE')) {
                iconClass = 'icon-close';
                direction = ageResult.includes('HIGH') ? '偏高' : '偏低';
            } else {
                direction = ageResult.includes('HIGH') ? '太高' : '太低';
            }

            detailsHtml += `
                <div class="result-item">
                    <span class="${iconClass}">●</span>
                    <span>年龄: ${ageValue} ${direction}</span>
                </div>
            `;
        }

        // 角色
        if (result.role) {
            const roleResult = result.role.result;
            const roleValue = result.role.value || '';
            let iconClass = roleResult === 'CORRECT' ? 'icon-correct' : 'icon-wrong';

            detailsHtml += `
                <div class="result-item">
                    <span class="${iconClass}">●</span>
                    <span>角色: ${roleValue}</span>
                </div>
            `;
        }

        // Major出场次数
        if (result.majorAppearances) {
            const majorResult = result.majorAppearances.result;
            const majorValue = result.majorAppearances.value || 0;
            let iconClass = 'icon-wrong';
            let direction = '';

            if (majorResult === 'CORRECT') {
                iconClass = 'icon-correct';
            } else if (majorResult.includes('CLOSE')) {
                iconClass = 'icon-close';
                direction = majorResult.includes('HIGH') ? '偏高' : '偏低';
            } else {
                direction = majorResult.includes('HIGH') ? '太高' : '太低';
            }

            detailsHtml += `
                <div class="result-item">
                    <span class="${iconClass}">●</span>
                    <span>Major出场: ${majorValue} ${direction}</span>
                </div>
            `;
        }

        return detailsHtml;
    }

    // 更新约束条件显示
    function updateConstraintsDisplay(constraintsData) {
        if (!constraintsData) return;

        currentConstraints = constraintsData;
        constraints.innerHTML = '';  // 现在这个constraints引用的是DOM元素

        for (const [key, value] of Object.entries(currentConstraints)) {
            const constraintItem = document.createElement('div');
            constraintItem.className = 'constraint-item';

            let constraintText = '';

            switch (key) {
                case 'nationality':
                    if (value.exact) {
                        constraintText = `必须是 ${value.exact}`;
                    } else if (value.exclude_list) {
                        constraintText = `不能是 ${value.exclude_list.join(', ')}`;
                    } else if (value.exclude) {
                        constraintText = `不能是 ${value.exclude}`;
                    }
                    break;

                case 'nationality_region':
                    if (value.region) {
                        constraintText = `必须在 ${value.region} 区域`;
                    }
                    break;

                case 'team':
                    if (value.exact) {
                        constraintText = `必须是 ${value.exact}`;
                    }
                    break;

                case 'age':
                    if (value.exact) {
                        constraintText = `必须是 ${value.exact} 岁`;
                    } else {
                        let range = '';
                        if (value.min) range += `>= ${value.min} `;
                        if (value.max) range += `<= ${value.max}`;
                        constraintText = range;
                    }
                    break;

                case 'role':
                    if (value.exact) {
                        constraintText = `必须是 ${value.exact}`;
                    } else if (value.exclude_list) {
                        constraintText = `不能是 ${value.exclude_list.join(', ')}`;
                    } else if (value.exclude) {
                        constraintText = `不能是 ${value.exclude}`;
                    }
                    break;

                case 'majorAppearances':
                    if (value.exact) {
                        constraintText = `必须是 ${value.exact} 次`;
                    } else {
                        let range = '';
                        if (value.min) range += `>= ${value.min} `;
                        if (value.max) range += `<= ${value.max}`;
                        constraintText = range + ' 次';
                    }
                    break;

                case 'isRetired':
                    if (value.exact !== undefined) {
                        constraintText = value.exact ? '必须已退役' : '必须未退役';
                    }
                    break;

                default:
                    constraintText = JSON.stringify(value);
            }

            constraintItem.innerHTML = `
                <div class="constraint-type">${getConstraintTypeName(key)}:</div>
                <div class="constraint-value">${constraintText}</div>
            `;

            constraints.appendChild(constraintItem);
        }
    }

    // 获取约束类型名称
    function getConstraintTypeName(key) {
        const typeMap = {
            'nationality': '国籍',
            'nationality_region': '区域',
            'team': '队伍',
            'age': '年龄',
            'role': '角色',
            'majorAppearances': 'Major出场',
            'isRetired': '退役状态'
        };

        return typeMap[key] || key;
    }

    // 获取阶段显示名称
    function getPhaseDisplayName(phase) {
        const phaseMap = {
            'ready': '准备中',
            'starting': '即将开始',
            'game': '猜测中',
            'end': '本轮结束',
            'completed': '游戏结束'
        };

        return phaseMap[phase] || phase || '未知';
    }

    // 减少剩余猜测次数
    function decrementGuessCounter() {
        remainingGuesses--;
        if (remainingGuesses < 0) remainingGuesses = 0;
        guessCounter.textContent = remainingGuesses;
    }

    // 显示成功消息
    function showSuccessMessage(result) {
        const successModal = document.createElement('div');
        successModal.className = 'success-modal';

        // 处理团队显示
        let teamDisplay = '无团队';
        if (result.team) {
            if (typeof result.team === 'object' && result.team !== null) {
                if (result.team.data) {
                    teamDisplay = typeof result.team.data === 'object' ?
                        (result.team.data.name || '未知团队') : result.team.data;
                } else {
                    teamDisplay = result.team.name || '未知团队';
                }
            } else {
                teamDisplay = result.team;
            }
        }

        successModal.innerHTML = `
            <div class="success-modal-content">
                <h2>恭喜，猜对了!</h2>
                <div class="success-player">
                    <img src="${result.image_url || 'https://via.placeholder.com/150?text=No+Image'}" alt="${result.nickname || ''}">
                    <div class="success-player-info">
                        <div class="success-player-name">${result.firstName || ''} ${result.lastName || ''}</div>
                        <div class="success-player-nickname">${result.nickname || ''}</div>
                        <div class="success-player-details">
                            ${result.nationality ? result.nationality.value || result.nationality : ''} | ${teamDisplay}<br>
                            ${result.role ? result.role.value || result.role : '未知角色'} | ${result.age ? result.age.value || result.age : '未知年龄'}
                        </div>
                    </div>
                </div>
                <button class="btn" id="closeSuccessBtn">关闭</button>
            </div>
        `;

        document.body.appendChild(successModal);

        document.getElementById('closeSuccessBtn').addEventListener('click', function () {
            document.body.removeChild(successModal);
        });
    }

    // 显示连接状态
    function showConnectionStatus(message, statusClass) {
        connectionStatus.textContent = message;
        connectionStatus.className = 'status ' + statusClass;
    }

    // 切换连接按钮状态
    function toggleConnectionButtons() {
        connectBtn.disabled = isConnected;
        disconnectBtn.disabled = !isConnected;
        readyBtn.disabled = !isConnected;

        // 重置按钮文本
        if (!isConnected) {
            readyBtn.textContent = '准备就绪';
        }
    }

    // 显示游戏面板
    function showGamePanel() {
        gamePanel.style.display = 'block';
    }

    // 隐藏游戏面板
    function hideGamePanel() {
        gamePanel.style.display = 'none';
    }

    // 重置游戏状态
    function resetGameState() {
        remainingGuesses = 8;
        guessCounter.textContent = remainingGuesses;
        playerList.innerHTML = '';
        guessResults.innerHTML = '';
        constraints.innerHTML = '';
        currentRecommendations = [];
        currentConstraints = {};
    }
});