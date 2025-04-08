import json
import time
import requests
from typing import Dict, Any

headers = {
    "authority": "api.blast.tv",
    "method": "POST",
    "path": "/v1/counterstrikle/guesses",
    "scheme": "https",
    "accept": "application/json, text/plain, */*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "content-type": "application/json",
    "origin": "https://blast.tv",
    "priority": "u=1, i",
    "referer": "https://blast.tv/",
    "sec-ch-ua": "\"Chromium\";v=\"134\", \"Not:A-Brand\";v=\"24\", \"Microsoft Edge\";v=\"134\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\"",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0"
}

base_url = "https://api.blast.tv/v1/counterstrikle/guesses"

def guess(player_id: str) -> Dict[str, Any]:
    """
    向Blast.tv API发送猜测请求并获取玩家信息
    
    Args:
        player_id (str): 玩家的唯一ID，格式为UUID
        
    Returns:
        Dict[str, Any]: 包含玩家信息和猜测结果的字典，包括:
            - id: 玩家ID
            - nickname: 玩家昵称
            - firstName: 玩家名
            - lastName: 玩家姓
            - isRetired: 是否退役
            - nationality: 国籍信息及猜测结果
            - team: 队伍信息及猜测结果
            - age: 年龄信息及猜测结果
            - majorAppearances: Major赛事出场次数及猜测结果
            - role: 角色信息及猜测结果
            - isSuccess: 猜测是否成功
    
    Raises:
        requests.exceptions.RequestException: 当请求失败时抛出
    """
    payload = {
        "playerId": player_id
    }
    
    response = requests.post(base_url, headers=headers, json=payload)
    response.raise_for_status()  # 如果响应状态码不是200，将引发异常
    
    return response.json()

def main():
    """
    主函数：读取players.json中的所有玩家ID，调用API获取详细信息，并保存结果
    """
    # 读取玩家数据
    input_file = 'players.json'
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            players = json.load(f)
    except FileNotFoundError:
        print(f"错误: 找不到文件 {input_file}")
        return
    except json.JSONDecodeError:
        print(f"错误: 无法解析 {input_file}, 确保它是有效的 JSON 格式")
        return
    
    result_data = []
    total_players = len(players)
    
    print(f"开始获取 {total_players} 名玩家的详细信息...")
    start_time = time.time()
    
    for i, player in enumerate(players):
        player_id = player["id"]
        try:
            # 调用 guess 函数获取玩家详细信息
            player_data = guess(player_id)
            
            # 提取所需信息
            result = {
                "id": player_data.get("id", ""),
                "nickname": player_data.get("nickname", ""),
                "firstName": player_data.get("firstName", ""),
                "lastName": player_data.get("lastName", ""),
                "isRetired": player_data.get("isRetired", False),
                "nationality": player_data.get("nationality", {}).get("value"),
                "team": player_data.get("team", {}).get("data"),
                "age": player_data.get("age", {}).get("value"),
                "majorAppearances": player_data.get("majorAppearances", {}).get("value"),
                "role": player_data.get("role", {}).get("value")
            }
            
            result_data.append(result)
            print(f"[{i+1}/{total_players}] 已获取 {result['nickname']} 的数据")
        
        except Exception as e:
            print(f"[{i+1}/{total_players}] 获取 {player['nickname']} 的数据失败: {str(e)}")
        
        # 每次调用后暂停 1 秒
        if i < total_players - 1:  # 最后一个玩家后不需要等待
            time.sleep(1)
    
    elapsed_time = time.time() - start_time
    print(f"\n数据获取完成，耗时: {elapsed_time:.2f} 秒")
    
    # 保存数据到新文件
    output_file = 'players_details.json'
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        print(f"数据已保存到 {output_file}")
    except Exception as e:
        print(f"保存数据时出错: {str(e)}")

if __name__ == "__main__":
    main()