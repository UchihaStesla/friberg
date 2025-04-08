import json
import os
import math
from collections import Counter

def compare_players(player1, player2):
    """
    比较两名玩家，返回五元组表示比较结果状态
    
    返回格式: (队伍状态, 国籍状态, 年龄状态, 职位状态, Major次数状态)
    """
    # 检查字段是否存在，避免KeyError
    if player1 == player2:
        return (0, 0, 0, 0, 0)  # 完全相同的玩家
    
    # 队伍状态比较
    team1 = player1.get("team", {})
    team2 = player2.get("team", {})
    
    if team1 is None or team2 is None:
        team_status = 1  # 如果任一方没有队伍，则视为不在同一队伍
    else:
        team1_id = team1.get("id") if isinstance(team1, dict) else None
        team2_id = team2.get("id") if isinstance(team2, dict) else None
        team_status = 0 if team1_id == team2_id and team1_id is not None else 1
    
    # 国籍状态比较
    nationality1 = player1.get("nationality", "")
    nationality2 = player2.get("nationality", "")
    nationality_status = 0 if nationality1 == nationality2 and nationality1 != "" else 1
    
    # 年龄状态比较
    age1 = player1.get("age", 0)
    age2 = player2.get("age", 0)
    
    if age1 == age2:
        age_status = 0
    elif age1 == 0 or age2 == 0:
        age_status = 0  # 如果任一方没有年龄数据，不进行比较
    else:
        age_diff = age2 - age1
        if abs(age_diff) <= 3:
            age_status = 1 if age_diff > 0 else -1  # 年龄接近
        else:
            age_status = 2 if age_diff > 0 else -2  # 年龄差距大
    
    # 职位状态比较
    role1 = player1.get("role", "")
    role2 = player2.get("role", "")
    role_status = 0 if role1 == role2 and role1 != "" else 1
    
    # Major次数状态比较
    major1 = player1.get("majorAppearances", 0)
    major2 = player2.get("majorAppearances", 0)
    
    if major1 == major2:
        major_status = 0
    elif major1 == 0 or major2 == 0:
        major_status = 0  # 如果任一方没有Major数据，不进行比较
    else:
        major_diff = major2 - major1
        if abs(major_diff) <= 1:
            major_status = 1 if major_diff > 0 else -1  # Major次数接近
        else:
            major_status = 2 if major_diff > 0 else -2  # Major次数差距大
    
    return (team_status, nationality_status, age_status, role_status, major_status)

def calculate_entropy(distributions):
    """计算信息熵"""
    if not distributions:
        return 0
    
    total = sum(distributions.values())
    entropy = 0
    for count in distributions.values():
        probability = count / total
        entropy -= probability * math.log2(probability)
    
    return entropy

def calculate_player_entropy(player, players_list):
    """计算一个玩家与候选名单比较时的信息熵"""
    # 统计与候选名单比较时可能的状态分布
    state_counter = Counter()
    
    for candidate in players_list:
        state = compare_players(player, candidate)
        state_counter[state] += 1
    
    # 计算信息熵
    entropy = calculate_entropy(state_counter)
    return entropy

def merge_player_data(players_file, entropy_file, output_file):
    """
    合并玩家详细信息和信息熵数据。
    
    Args:
        players_file (str): 玩家详细信息的JSON文件路径
        entropy_file (str): 信息熵数据的JSON文件路径
        output_file (str): 输出合并结果的JSON文件路径
    """
    # 读取玩家详细信息
    with open(players_file, 'r', encoding='utf-8') as f:
        players_data = json.load(f)
    
    # 读取信息熵数据
    with open(entropy_file, 'r', encoding='utf-8') as f:
        entropy_data = json.load(f)
    
    # 提取entropy_data中的玩家名称和对应的信息熵
    entropy_values = {}
    rank_counter = 1
    
    # 处理entropy_data结构
    for player in entropy_data["players"]:
        if "name" not in player and "entropy" in player:
            # 处理只包含entropy的情况
            entropy_values[f"Player{rank_counter}"] = {
                "rank": rank_counter,
                "entropy": player["entropy"]
            }
            rank_counter += 1
        elif "name" in player and "entropy" in player:
            entropy_values[player["name"]] = {
                "rank": player["rank"] if "rank" in player else rank_counter,
                "entropy": player["entropy"]
            }
            rank_counter += 1
    
    # 匹配和合并数据
    matched_count = 0
    unmatched_players = []
    
    # 为每个玩家添加信息熵数据
    for player in players_data:
        nickname = player.get("nickname", "")
        if nickname in entropy_values:
            player["entropy_rank"] = entropy_values[nickname]["rank"]
            player["entropy_value"] = entropy_values[nickname]["entropy"]
            matched_count += 1
        else:
            unmatched_players.append(player)
            # 为未匹配的玩家计算信息熵
            calculated_entropy = calculate_player_entropy(player, players_data)
            player["entropy_rank"] = None
            player["entropy_value"] = calculated_entropy
            player["entropy_calculated"] = True  # 标记为计算得到的值
    
    # 将合并后的数据写入新文件
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(players_data, f, indent=2, ensure_ascii=False)
    
    print(f"合并完成！结果已保存至 {output_file}")
    print(f"总玩家数: {len(players_data)}")
    print(f"成功匹配: {matched_count}")
    print(f"未匹配(已计算信息熵): {len(unmatched_players)}")
    
    if unmatched_players:
        print("\n未找到匹配的玩家(前10名):")
        for i, player in enumerate(unmatched_players[:10], 1):
            nick = player.get("nickname", "未知")
            entropy = player.get("entropy_value", 0)
            print(f"{i}. {nick} (计算得到的信息熵: {entropy:.4f})")
        
        if len(unmatched_players) > 10:
            print(f"...等共 {len(unmatched_players)} 名玩家")

if __name__ == "__main__":
    base_dir = r"c:\Users\Stesla\Desktop\CODE\friberg"
    players_file = os.path.join(base_dir, "players_details.json")
    entropy_file = os.path.join(base_dir, "infor_entropy.json")
    output_file = os.path.join(base_dir, "players_with_entropy.json")
    
    merge_player_data(players_file, entropy_file, output_file)