#!/bin/bash
set -euo pipefail

# 配置参数
PYTHON_VERSION="3.11"
ENV_NAME="auto-register"
PROJECT_DIR=$(cd "$(dirname "$0")" && pwd)
REQUIREMENTS_FILE="${PROJECT_DIR}/requirements.txt"
START_SCRIPT="${PROJECT_DIR}/start.sh"
STOP_SCRIPT="${PROJECT_DIR}/stop.sh"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=============================================${NC}"
echo -e "${YELLOW}Auto-Registration-Engine 环境自动部署脚本${NC}"
echo -e "${YELLOW}当前系统: Linux (Ubuntu/Debian)${NC}"
echo -e "${YELLOW}目标 Python 版本: ${PYTHON_VERSION}${NC}"
echo -e "${YELLOW}=============================================${NC}"

# 1. 检查系统类型
if ! command -v apt &> /dev/null; then
    echo -e "${RED}错误: 仅支持 Ubuntu/Debian 系统${NC}"
    exit 1
fi

# 2. 更新系统源
echo -e "${YELLOW}[1/8] 更新系统软件源...${NC}"
sudo apt update -y
sudo apt install software-properties-common -y

# 3. 添加 Python 3.11 源
echo -e "${YELLOW}[2/8] 添加 Python ${PYTHON_VERSION} 官方源...${NC}"
if ! add-apt-repository -y ppa:deadsnakes/ppa; then
    echo -e "${RED}错误: 添加 Python 源失败${NC}"
    exit 1
fi
sudo apt update -y

# 4. 安装 Python 3.11 + venv
echo -e "${YELLOW}[3/8] 安装 Python ${PYTHON_VERSION} 及虚拟环境工具...${NC}"
sudo apt install -y python${PYTHON_VERSION} python${PYTHON_VERSION}-venv python${PYTHON_VERSION}-dev

# 5. 创建虚拟环境
echo -e "${YELLOW}[4/8] 创建独立虚拟环境: ${ENV_NAME}${NC}"
cd "${PROJECT_DIR}"
python${PYTHON_VERSION} -m venv "${ENV_NAME}"

# 6. 激活环境并升级 pip
echo -e "${YELLOW}[5/8] 升级 pip 到最新版本...${NC}"
source "${PROJECT_DIR}/${ENV_NAME}/bin/activate"
pip install --upgrade pip -i https://pypi.mirrors.ustc.edu.cn/simple/

# 7. 安装项目依赖
echo -e "${YELLOW}[6/8] 安装项目依赖...${NC}"
if [ ! -f "${REQUIREMENTS_FILE}" ]; then
    echo -e "${RED}错误: 未找到 requirements.txt${NC}"
    exit 1
fi
pip install -r "${REQUIREMENTS_FILE}" -i https://pypi.mirrors.ustc.edu.cn/simple/

# 8. 生成一键启动/停止脚本
echo -e "${YELLOW}[7/8] 生成一键启动/停止脚本...${NC}"

# 生成 start.sh
cat > "${START_SCRIPT}" << EOF
#!/bin/bash
# Auto-Registration-Engine 一键启动脚本
PROJECT_DIR="${PROJECT_DIR}"
ENV_NAME="${ENV_NAME}"
LOG_FILE="\${PROJECT_DIR}/run.log"

# 进入项目目录
cd "\${PROJECT_DIR}"

# 激活虚拟环境
source "\${PROJECT_DIR}/\${ENV_NAME}/bin/activate"

# 停止旧进程
pkill -f main.py > /dev/null 2>&1 || true

# 后台启动，日志写入文件
nohup python main.py >> "\${LOG_FILE}" 2>&1 < /dev/null &

# 输出启动信息
PID=\$(ps aux | grep main.py | grep -v grep | awk '{print \$2}')
echo -e "\033[0;32m✅ 项目已启动，PID: \${PID}\033[0m"
echo -e "\033[0;32m📝 日志文件: \${LOG_FILE}\033[0m"
echo -e "\033[0;32m🔍 实时查看日志: tail -f \${LOG_FILE}\033[0m"
EOF

# 生成 stop.sh
cat > "${STOP_SCRIPT}" << EOF
#!/bin/bash
# Auto-Registration-Engine 一键停止脚本
echo -e "\033[0;33m正在停止 main.py 进程...\033[0m"
pkill -f main.py
echo -e "\033[0;32m✅ 项目已停止\033[0m"
EOF

# 赋予执行权限
chmod +x "${START_SCRIPT}"
chmod +x "${STOP_SCRIPT}"

# 9. 部署完成
echo -e "${YELLOW}[8/8] 部署完成！${NC}"
echo -e "${GREEN}=============================================${NC}"
echo -e "${GREEN}✅ 环境部署成功！${NC}"
echo -e "${GREEN}📁 项目目录: ${PROJECT_DIR}${NC}"
echo -e "${GREEN}🐍 Python 版本: \$(python --version)${NC}"
echo -e "${GREEN}📦 虚拟环境: ${PROJECT_DIR}/${ENV_NAME}${NC}"
echo -e "${GREEN}🚀 一键启动: ./start.sh${NC}"
echo -e "${GREEN}🛑 一键停止: ./stop.sh${NC}"
echo -e "${GREEN}📝 日志文件: ${PROJECT_DIR}/run.log${NC}"
echo -e "${GREEN}=============================================${NC}"

# 退出虚拟环境
deactivate