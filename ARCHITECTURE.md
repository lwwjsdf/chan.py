# 缠论分析框架架构设计

## 核心原则
1. **单一职责**：每个模块只做一件事
2. **可复用**：核心逻辑不重复编写
3. **可扩展**：支持多种数据源、多种分析维度
4. **可配置**：通过配置驱动，不写死逻辑

## 目录结构

```
chan.py/
├── Core/                    # 核心框架（不变）
│   ├── ChanAnalyzer.py      # 分析器基类
│   ├── ChanConfig.py        # 配置管理
│   └── ChanScanner.py       # 扫描器基类
│
├── Strategies/              # 分析策略（可扩展）
│   ├── BSP2Scanner.py       # 二类买点扫描
│   ├── TrendScanner.py      # 趋势扫描
│   └── DivergenceScanner.py # 背驰扫描
│
├── DataProviders/           # 数据源（可扩展）
│   ├── PgStockProvider.py   # PostgreSQL数据源
│   ├── CsvProvider.py       # CSV数据源
│   └── AkshareProvider.py   # AKShare数据源
│
├── Outputs/                 # 输出管理
│   ├── CsvOutput.py         # CSV输出
│   ├── ChartOutput.py       # 图表输出
│   └── ReportOutput.py      # 报告输出
│
├── cli.py                   # 统一命令行入口
└── config.yaml              # 全局配置文件
```

## 核心类设计

### 1. ChanAnalyzer（分析器基类）

```python
class ChanAnalyzer:
    """缠论分析器基类"""
    
    def __init__(self, config: ChanConfig):
        self.config = config
        self.chan = None
        
    def analyze(self, code: str, data_provider) -> AnalysisResult:
        """分析单只股票"""
        # 1. 加载数据
        # 2. 构建Chan对象
        # 3. 执行分析
        # 4. 返回结果
        pass
    
    def get_buy_points(self) -> List[BuyPoint]:
        """获取所有买点"""
        pass
    
    def get_sell_points(self) -> List[SellPoint]:
        """获取所有卖点"""
        pass
```

### 2. ChanScanner（扫描器基类）

```python
class ChanScanner:
    """缠论扫描器基类"""
    
    def __init__(self, analyzer: ChanAnalyzer, data_provider):
        self.analyzer = analyzer
        self.data_provider = data_provider
        self.results = []
        
    def scan(self, codes: List[str], filter_func=None) -> ScanResult:
        """扫描多只股票"""
        for code in codes:
            try:
                result = self.analyzer.analyze(code, self.data_provider)
                if filter_func and filter_func(result):
                    self.results.append(result)
            except Exception as e:
                logger.error(f"扫描 {code} 失败: {e}")
        
        return ScanResult(self.results)
    
    def scan_batch(self, codes: List[str], batch_size=50, workers=4) -> ScanResult:
        """并行扫描"""
        # 使用多进程并行处理
        pass
```

### 3. 策略模式

```python
class BSP2Strategy:
    """二类买点策略"""
    
    def filter(self, result: AnalysisResult) -> bool:
        """判断是否满足二类买点条件"""
        bsp2_list = result.get_bsp2_list()
        if not bsp2_list:
            return False
        
        latest_bsp2 = bsp2_list[-1]
        # 检查是否在最近N天内
        return self.is_recent(latest_bsp2, days=30)
    
    def is_recent(self, bsp, days=30) -> bool:
        """检查买点是否近期"""
        pass

class TrendStrategy:
    """趋势策略"""
    
    def filter(self, result: AnalysisResult) -> bool:
        """判断趋势状态"""
        pass
```

## 使用示例

```python
# 1. 初始化配置
config = ChanConfig.from_yaml("config.yaml")

# 2. 选择数据源
provider = PgStockProvider(DB_CONFIG)

# 3. 创建分析器
analyzer = ChanAnalyzer(config)

# 4. 创建扫描器
scanner = ChanScanner(analyzer, provider)

# 5. 选择策略
strategy = BSP2Strategy(recent_days=30)

# 6. 执行扫描
codes = provider.get_all_codes()
result = scanner.scan(codes, filter_func=strategy.filter)

# 7. 输出结果
output = CsvOutput("/path/to/output.csv")
output.write(result)

# 8. 生成图表
for item in result.top(10):
    chart = ChartOutput(item.code)
    chart.generate()
```

## 配置示例

```yaml
# config.yaml
analysis:
  default_begin: "2025-09-04"
  kl_type: "K_DAY"
  
scanner:
  batch_size: 50
  workers: 4
  timeout: 120

strategies:
  bsp2:
    enabled: true
    recent_days: 30
    min_gain: -5
    max_gain: 50
  
  trend:
    enabled: false
    direction: "up"

output:
  format: "csv"
  path: "/Users/liwei/Workspace/A股交易/outputs/"
  
chart:
  enabled: true
  plot_config:
    plot_kline: true
    plot_bi: true
    plot_seg: true
    plot_zs: true
    plot_bsp: true
    plot_macd: true
```

## 命令行接口

```bash
# 扫描二类买点
python cli.py scan --strategy bsp2 --recent-days 30

# 扫描趋势
python cli.py scan --strategy trend --direction up

# 分析单只股票
python cli.py analyze 000063 --chart

# 批量生成图表
python cli.py chart --input results.csv

# 查看报告
python cli.py report --date 2026-06-15
```

## 核心优势

1. **不重复造轮子**
   - ChanAnalyzer 只写一次
   - 所有扫描器复用同一分析器
   - 数据源统一接口

2. **策略可插拔**
   - 新增策略只需实现 filter 方法
   - 策略组合使用
   - A/B测试不同策略

3. **并行处理**
   - 自动分批
   - 多进程并行
   - 错误隔离

4. **统一输出**
   - CSV、图表、报告格式统一
   - 支持多种输出方式
   - 结果可追踪

## 下一步实施

1. 将现有代码重构为上述架构
2. 提取公共逻辑到 Core 模块
3. 实现策略模式
4. 统一命令行接口
5. 编写配置文件

这样以后新增功能只需：
- 新增策略类（30行代码）
- 修改配置文件
- 无需修改核心逻辑

---

## 2026-06 重构说明

`chan.py` 只保留缠论核心能力。业务逻辑层已全部迁移至 `stockmind/`：

| 原脚本 | 新位置 / 状态 |
|---|---|
| `scan_watchlist_bsp.py` | → `stockmind/scripts/daily_bsp_scan.py` |
| `chan_viewer.py` | 保留，通过 chan_api 调用 |
| `analyze_stock_bsp.py` | 保留，通过 chan_api 调用 |
| `scan_tech_bsp2.py` | 废弃（旧版扫描） |
| `scan_all_bsp2.py` | 废弃 |
| `scan_bsp2_detailed.py` | 废弃 |
| `scan_bsp2_framework.py` | 废弃 |
| `scan_bsp2_parallel.py` | 废弃 |
| `run_test.py` | 废弃 |
| `test_bsp.py` | 废弃 |
| `test_bsp2.py` | 废弃 |

`chan_api.py` 是唯一对外接口，业务层不得直接 import CChan。
