import os
import error
import json

config = json.load(open("config.json", "r"))

# 楼层映射：将楼层名称映射为数字，用于相邻移动判断
floor_mapping = {
    "B4": 1, "B3": 2, "B2": 3, "B1": 4,
    "F1": 5, "F2": 6, "F3": 7, "F4": 8, "F5": 9, "F6": 10, "F7": 11
}

class Req:
    def __init__(self, req):
        eles = self.parseReq(req)
        # 解析后的各项依次为：
        # [0] passenger_id, [1] "PRI", [2] priority, [3] "FROM", [4] from_floor, 
        # [5] "TO", [6] to_floor, [7] "BY", [8] elevator id
        self.passenger_id = int(eles[0])
        self.priority = int(eles[2])
        self.from_floor = eles[4]
        self.to_floor = eles[6]
        self.ele_id = int(eles[8])
        self.request_time = float(req[1:req.index(']')].strip())
    
    def parseReq(self, req):
        req = req.replace('\n', '')
        index = req.index(']')
        req = req[index+1:]
        return req.split('-')

    def getUserId(self):
        return self.passenger_id

    def getPriority(self):
        return self.priority

    def getFromFloor(self):
        return self.from_floor

    def getToFloor(self):
        return self.to_floor

    def getEleId(self):
        return self.ele_id
    
    def getRequestTime(self):
        return self.request_time

STATE_OPEN = 0
STATE_CLOSE = 1
# 楼层在映射后范围为1～11
MIN_FLOOR = 1
MAX_FLOOR = 11
MAX_NUM = 6

reqDict = {}
reqDict_backup = {}
floors = []
states = []
passengers = []
lastMoveTime = []
lastOpenTime = []
# 为每部电梯保存上一次操作的时间（用于门开关、移动操作间隔判断）
elevator_last_op_time = []
# 全局输出时间，用于确保所有输出行时间严格递增
global_last_op_time = -10.0
flag = [0]
    
def check(input_str, output_str, name):
    initElevator()
    processInput(input_str)
    flag[0] = 1
    count = 1
    
    # 存储计算性能所需的数据
    arrive_count = 0
    open_count = 0
    close_count = 0
    passenger_metrics = []
    
    lines = output_str.split('\n')
    for line in lines:
        if line != "":
            res = process(line, count)
            count += 1
            if not res[0]:
                error.error_output(name, res[1], input_str, output_str, "Line: " + str(res[2]))
                return False, 0, 0
            
            if line.startswith("[") and "]" in line:
                op_time = float(line[1:line.index("]")].strip())
                content = line[line.index("]")+1:]
                
                if content.startswith("ARRIVE"):
                    arrive_count += 1
                elif content.startswith("OPEN"):
                    open_count += 1
                elif content.startswith("CLOSE"):
                    close_count += 1
                elif content.startswith("OUT"):
                    # 计算下车乘客的等候时间
                    passenger_id = int(content.split('-')[1])
                    req = reqDict_backup.get(passenger_id)
                    if req:
                        completion_time = op_time - req.getRequestTime()
                        passenger_metrics.append((req.getPriority(), completion_time))
    
    if len(reqDict) != 0:
        missing = ""
        for req in reqDict.values():
            missing += str(req.getUserId()) + "\n"
        error.error_output(name, "Not all requests are processed", input_str, output_str, "Missing: " + missing)
        return False, 0, 0
    
    for i in range(6):
        if len(passengers[i]) != 0:
            error.error_output(name, "Someone is trapped in elevator", input_str, output_str, "Elevator ID: " + str(i + 1))
            return False, 0, 0
        if states[i] != STATE_CLOSE:
            error.error_output(name, "Elevator door is not close", input_str, output_str, "Elevator ID: " + str(i + 1))
            return False, 0, 0
    
    # 计算性能
    W_ARRIVE = 0.4
    W_OPEN = 0.1
    W_CLOSE = 0.1
    total_power = (W_ARRIVE * arrive_count + 
                   W_OPEN * open_count + 
                   W_CLOSE * close_count)

    if passenger_metrics:
        sum_weighted_time = sum(p * t for p, t in passenger_metrics)
        sum_weights = sum(p for p, t in passenger_metrics)
        wt = sum_weighted_time / sum_weights
    else:
        wt = 0
    
    return True, total_power, wt

def initElevator():
    global global_last_op_time
    reqDict.clear()
    floors.clear()
    states.clear()
    passengers.clear()
    lastMoveTime.clear()
    lastOpenTime.clear()
    elevator_last_op_time.clear()
    global_last_op_time = -10.0
    flag[0] = 0
    # 初始楼层设为 "F1"（映射值5），所有电梯门初始状态均为关闭
    for i in range(6):
        floors.append(floor_mapping["F1"])
        states.append(STATE_CLOSE)
        passengers.append([])
        lastMoveTime.append(-10.0)
        lastOpenTime.append(-10.0)
        elevator_last_op_time.append(0.0)

def processInput(input_str):
    tot = input_str.split('\n')
    for ele in tot:
        if ele == "":
            break
        req = Req(ele)
        reqDict[req.getUserId()] = req
        reqDict_backup[req.getUserId()] = req

def process(read, lineNum):
    global global_last_op_time
    # 去除换行后解析时间
    read = read.replace('\n', '')
    index = read.index(']')
    # 提取时间部分，支持固定宽度格式（如 "[   1.4200]"）
    opTime = float(read[1:index].strip())
    # 检查全局输出时间顺序
    if opTime < global_last_op_time:
        return False, "INCORRECT OUTPUT ORDER!", lineNum
    global_last_op_time = opTime

    # 提取操作内容，按 "-" 分割
    content = read[index+1:]
    eles = content.split('-')
    
    if eles[0] == 'ARRIVE':
        # 格式：ARRIVE-{楼层}-{电梯编号}
        if len(eles) != 3:
            return False, "ARRIVE FORMAT ERROR!", lineNum
        floor_str = eles[1]
        new_floor = floor_mapping.get(floor_str)
        if new_floor is None:
            return False, "ELEVATOR ON A NON-EXISTENT FLOOR!", lineNum
        index_elevator = int(eles[2]) - 1
        if not 0 <= index_elevator < 6:
            return False, "UNKNOWN ELEVATOR ID!", lineNum
        if states[index_elevator] != STATE_CLOSE:
            return False, "MOVE WHEN DOOR IS NOT CLOSE!", lineNum
        if opTime - lastMoveTime[index_elevator] < 0.4 - float(config["fault_tolerance"]):
            return False, "MOVE TOO FAST!", lineNum
        if abs(floors[index_elevator] - new_floor) != 1:
            return False, "ELEVATOR MOVE TOO FAST!", lineNum
        lastMoveTime[index_elevator] = opTime
        floors[index_elevator] = new_floor

    elif eles[0] == 'OPEN':
        # 格式：OPEN-{楼层}-{电梯编号}
        if len(eles) != 3:
            return False, "OPEN FORMAT ERROR!", lineNum
        floor_str = eles[1]
        expected_floor = floor_mapping.get(floor_str)
        if expected_floor is None:
            return False, "ELEVATOR ON A NON-EXISTENT FLOOR!", lineNum
        index_elevator = int(eles[2]) - 1
        if not 0 <= index_elevator < 6:
            return False, "UNKNOWN ELEVATOR ID!", lineNum
        if states[index_elevator] != STATE_CLOSE:
            return False, "ELEVATOR ALREADY OPEN!", lineNum
        states[index_elevator] = STATE_OPEN
        elevator_last_op_time[index_elevator] = opTime
        lastOpenTime[index_elevator] = opTime
        if floors[index_elevator] != expected_floor:
            return False, "ELEVATOR UNMATCHED FLOOR!", lineNum

    elif eles[0] == 'CLOSE':
        # 格式：CLOSE-{楼层}-{电梯编号}
        if len(eles) != 3:
            return False, "CLOSE FORMAT ERROR!", lineNum
        floor_str = eles[1]
        expected_floor = floor_mapping.get(floor_str)
        if expected_floor is None:
            return False, "ELEVATOR ON A NON-EXISTENT FLOOR!", lineNum
        index_elevator = int(eles[2]) - 1
        if not 0 <= index_elevator < 6:
            return False, "UNKNOWN ELEVATOR ID!", lineNum
        if states[index_elevator] != STATE_OPEN:
            return False, "ELEVATOR ALREADY CLOSE!", lineNum
        # 检查门开启时间
        if opTime - lastOpenTime[index_elevator] < 0.4 - 0.00001:
            return False, "CLOSE TOO FAST!", lineNum
        states[index_elevator] = STATE_CLOSE
        elevator_last_op_time[index_elevator] = opTime
        if floors[index_elevator] != expected_floor:
            return False, "ELEVATOR UNMATCHED FLOOR!", lineNum

    elif eles[0] == 'IN':
        # 格式：IN-{乘客ID}-{楼层}-{电梯编号}
        if len(eles) != 4:
            return False, "IN FORMAT ERROR!", lineNum
        passenger_id = int(eles[1])
        floor_str = eles[2]
        expected_floor = floor_mapping.get(floor_str)
        if expected_floor is None:
            return False, "ELEVATOR ON A NON-EXISTENT FLOOR!", lineNum
        index_elevator = int(eles[3]) - 1
        if not 0 <= index_elevator < 6:
            return False, "UNKNOWN ELEVATOR ID!", lineNum
        if states[index_elevator] != STATE_OPEN:
            return False, "PASSENGER IN WHEN DOOR IS NOT OPEN!", lineNum
        if floors[index_elevator] != expected_floor:
            return False, "ELEVATOR UNMATCHED FLOOR!", lineNum
        req = reqDict.get(passenger_id)
        if req is None:
            return False, "PASSENGER NOT EXIST!", lineNum
        # 检查 IN 操作楼层是否与请求中出发楼层匹配
        if req.getFromFloor() != floor_str:
            return False, "IN MESSAGE NOT MATCH REQUEST!", lineNum
        if len(passengers[index_elevator]) >= MAX_NUM:
            return False, "ELEVATOR OVERLOAD!", lineNum
        passengers[index_elevator].append(passenger_id)

    elif eles[0] == 'OUT':
        # 格式：OUT-{乘客ID}-{楼层}-{电梯编号}
        if len(eles) != 4:
            return False, "OUT FORMAT ERROR!", lineNum
        passenger_id = int(eles[1])
        floor_str = eles[2]
        expected_floor = floor_mapping.get(floor_str)
        if expected_floor is None:
            return False, "ELEVATOR ON A NON-EXISTENT FLOOR!", lineNum
        index_elevator = int(eles[3]) - 1
        if not 0 <= index_elevator < 6:
            return False, "UNKNOWN ELEVATOR ID!", lineNum
        if states[index_elevator] != STATE_OPEN:
            return False, "PASSENGER OUT WHEN DOOR IS NOT OPEN!", lineNum
        if passenger_id not in passengers[index_elevator]:
            return False, "PASSENGER NOT IN ELEVATOR!", lineNum
        passengers[index_elevator].remove(passenger_id)
        req = reqDict.get(passenger_id)
        if req is None:
            return False, "PASSENGER NOT EXIST!", lineNum
        # 检查 OUT 操作楼层是否与请求中目标楼层匹配
        if req.getToFloor() != floor_str:
            return False, "OUT MESSAGE NOT MATCH REQUEST!", lineNum
        reqDict.pop(passenger_id)

    else:
        return False, "UNKNOWN OPTIONS!", lineNum

    return True, "Accepted", lineNum