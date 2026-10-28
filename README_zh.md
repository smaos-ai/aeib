# 🏛️ SMAOS / AEIB 智能体清算验证引擎与线缆真实性观测器

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Zero-Egress Verified](https://img.shields.io/badge/数据不出域-0字节外发(气隙隔离)-success.svg)]()
[![Compliance: DORA Art. 17](https://img.shields.io/badge/EU_DORA-RTS_2024%2F1772-orange.svg)]()
[![Standard: CAICT ATH 1.0](https://img.shields.io/badge/中国信通院-ATH_1.0_可信握手-green.svg)]()
[![Stack: Java 21+ | Spring Boot | Python](https://img.shields.io/badge/运行时-Java_21+_|_Python_|_MCP-informational.svg)]()

> **自主 AI 智能体（Agent）的主权清算与真实性验证层：**  
> 现有的智能体开发框架几乎都会在本地日志记录 `CONFIRMED`（已确认）。但在真实网络故障下（HTTP 504 网关超时、TCP RST 异常断连），绝大多数智能体并没有检测到底层金融或业务系统是否真正完成了状态清算。  
> `aeib-receipt-fuzzer` 是一个纯本地运行、气隙隔离的线缆级故障注入与验证引擎，拦截智能体工具调用，模拟网络降级，捕获虚假确认，并生成符合监管标准的可信审计凭据。

---

## ⚡ 60秒本地气隙极速启动 (无外部依赖)

基于纯 Python 标准库开发，零外部 pip 包依赖，完全在 `127.0.0.1` 本地环回接口执行，内存级自动脱敏敏感数据（支持 PCI-DSS / GDPR 脱敏）：

```bash
# 克隆并在本地执行线缆模糊测试与脱敏套件
git clone https://github.com/sovereignnexus/aeib-receipt-fuzzer.git
cd aeib-receipt-fuzzer
python3 run.py --all-scenarios --export-dir ./audit_out
```

**输出产物：** 自动生成实时 Mermaid 时序轨迹图、欧盟 DORA 第17条重大事件差距报告、以及企业级 Java 21 (Spring Boot WebClient) 和 Python 即插即用防御过滤器。

---

## 👔 企业核心三大法律与财务风险对齐

| 企业核心风险 | 生产环境失效模式 | 监管与财务损失 | SMAOS 确定性防护机制 |
| :--- | :--- | :--- | :--- |
| **1. 虚假确认与静默双花** | 智能体发起清算调用，网关返回 HTTP 504 超时；SDK 吞掉异常误报 `CONFIRMED` 并触发重复重试。 | 导致清算账本失衡（$\sum \Delta_{\text{net}} \neq 0.00$），凌晨4点夜间对账全面崩溃。 | **强制降级不变式：** 线缆凭证缺失强制锁定为不可篡改的 `UNKNOWN`（未知）挂起状态。 |
| **2. 影子 MCP 工具漂移** | 工具维护者推送未经声明的权限更新（OWASP MCP03 "Rug Pull" 工具提权）。 | 未授权访问底层数据库，数据外泄，违反《人工智能法案》与安全基线。 | **Schema 哈希锚定：** 锁定 `mcp.json` 的 SHA-256 摘要，检测到漂移立即切断执行。 |
| **3. 跨域 A2A 委托无存证** | 智能体 A 跨系统委托智能体 B；智能体 B 静默失败并伪造凭证。 | 违反 ISO/IEC 42001 第9条以及中国信通院 ATH 1.0 行为溯源要求。 | **签名凭据闭包：** 绑定上游 A2A DID 身份至下游 SCITT / AFiR 存证中。 |

---

## 🌐 中国信通院 ATH 1.0 与跨司法管辖区映射

本系统是全球首个原生统一中欧美三方监管标准的线缆验证引擎：

* **中国 CAICT ATH 1.0 (智能体可信握手协议):** 完整映射三方（用户–智能体–服务）9步去中心化握手协议，网关丢包自动对齐为 `SERVICE_UNOBSERVABLE`。
* **欧盟 DORA (RTS 2024/1772 第17条):** 自动生成符合监管4小时重大事件通报时限的 `dora_art17_gap_report.json`。
* **美国 NIST RMF (SP 800-53 Rev. 5):** 强制执行 `CP-10` 应急保持与 `SI-7` 系统完整性校验。

---

## ☕ 企业级多语言修复补丁

### 1. Java 21+ / Spring Boot 反应式过滤器 (`ProofOrStopFilter.java`)
针对银行与核心交易系统（Spring AI / LangChain4j）：
```java
public class ProofOrStopFilter implements ExchangeFilterFunction {
    @Override
    public Mono<ClientResponse> filter(ClientRequest request, ExchangeFunction next) {
        return next.exchange(request)
            .onErrorResume(java.net.SocketTimeoutException.class, ex -> {
                // 核心硬性边界不变式：凭证缺失 => UNKNOWN
                return Mono.error(new AgentDiscrepancyException(
                    "DORA Art. 17 / ATH 1.0 违规: 网络超时且无清算回执，状态强制设为 UNKNOWN。"
                ));
            });
    }
}
```

### 2. Python 装饰器 (`fix.patch`)
```python
@proof_or_stop(enforce_unknown_on_504=True)
def settle_transaction(payload: dict) -> dict:
    return dispatch_to_wire(payload)
```

---

## 💼 定额 Staging 阶段验证评估服务

* **第一阶段：48小时诊断性评估（€1,500 / 约 11,500 RMB）：** 气隙导入 250+ 条测试环境轨迹，计算毒性凭据指数（TRI %），定位虚假确认风险。
* **第二阶段：5天深度对账司法审计（€2,500 / 约 19,000 RMB）：** 针对测试环境实施 6 种线缆级故障注入，交付 DORA 第17条差距评估报告及定制 Java/Python 修复过滤器。

📩 **商务咨询与预约评估：** `andrii@sovereignnexus.org` / `andrejlo123@gmail.com`
