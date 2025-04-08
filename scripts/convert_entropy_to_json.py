import json
import re

def convert_entropy_to_json(input_file, output_file):
    players_data = []
    
    # 读取文本文件
    with open(input_file, 'r') as f:
        lines = f.readlines()
    
    # 解析每一行数据
    for line in lines:
        # 使用正则表达式匹配每行的格式：序号: 玩家ID 信息熵值
        match = re.match(r'(\d+): (\S+) ([\d.]+)', line.strip())
        if match:
            rank = int(match.group(1))
            player_name = match.group(2)
            entropy_value = float(match.group(3))
            
            player_info = {
                "rank": rank,
                "name": player_name,
                "entropy": entropy_value
            }
            
            players_data.append(player_info)
    
    # 创建结构化数据
    data = {
        "title": "CS:GO Players Information Entropy",
        "total_players": len(players_data),
        "players": players_data
    }
    
    # 写入JSON文件
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"转换完成！数据已保存至 {output_file}")
    print(f"共处理 {len(players_data)} 名玩家数据")

if __name__ == "__main__":
    input_file = "c:\\Users\\Stesla\\Desktop\\CODE\\friberg\\infor_entropy.txt"
    output_file = "c:\\Users\\Stesla\\Desktop\\CODE\\friberg\\infor_entropy.json"
    convert_entropy_to_json(input_file, output_file)