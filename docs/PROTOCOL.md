# Protocolo de configuração LAMZU — evidências técnicas

Engenharia reversa do configurador oficial para Windows, com o objetivo de portá-lo
para macOS. Cada afirmação abaixo traz sua fonte e o tipo de evidência:

- **[E]** estática: lida no binário (metadados .NET, IL ou assembly x64)
- **[H]** hardware: observada num receptor LAMZU 4K real (PID `0xF510`, firmware do mouse 1.24)
- **[I]** inferida: coerente com as evidências, mas não observada diretamente

## 1. Artefatos analisados

| Arquivo | SHA-256 | O que é |
|---|---|---|
| `Mouse Drive Beta.exe` (5,35 MB) | `bef7609e…2521fb052` | UI WinForms, .NET Framework 4.8, AnyCPU, **sem assinatura** [E] |
| `HIDUsb.dll` (x64, embutida) | `abbc0a81…b7a9e6e1` | camada nativa com todo o protocolo HID [E] |
| `HIDUsb32.dll` (x86, embutida) | `09bb39ac…6ee6720fc` | mesma camada, build 32 bits [E] |
| `Config.ini` | — | lista de modelos, VID/PIDs (em Base64), faixas de DPI [E] |
| `driver_sensor.h` | — | tabelas de DPI de outros sensores (3335/3325/3104/3212); não usadas pelo 3395 [E] |

Evidências REA (sessão de análise): `ev_8b44a779…` (classificação do assembly e
recursos), `ev_879b3be7…` (222 P/Invokes), `ev_25793954…` (tipos, campos e enums).

### Observações de empacotamento

- As DLLs nativas **não estão no disco**: são recursos gerenciados embutidos com
  Costura.Fody (`costura64.hidusb.dll`, `costura32.hidusb32.dll`) e extraídas em tempo
  de execução. `tools/re/extract_res.py` as recupera (RVA dos recursos `0x43E98`). [E]
- `kernel32.dll`, `user32.dll` e `oleaut32.dll` na pasta de instalação são cópias
  legítimas assinadas pela Microsoft (build 19041). É descuido de empacotamento, não
  sideloading malicioso; `kernel32` é KnownDLL e nunca é carregada dali. [E]
- `UsbFile.dll` e `AES.dll` são referenciadas por P/Invoke, mas não são distribuídas:
  servem à ferramenta de atualização de firmware, fora do escopo deste port. [E]
- O app não tem serviço, driver de kernel, pipe nomeado nem socket. A única "IPC"
  é o HID. [E]

## 2. Arquitetura do app original

```
WinForms (FormMain, DPIControl, …)          C#  — DriverLib.*  (UsbServer, DataParser)
        │  P/Invoke cdecl (CS_UsbServer_*, CS_ProtocolData*)
        ▼
HIDUsb.dll ── fila de comandos (vetor de entradas de 20 B, mutex em 0x18002a550)
        │       thread de I/O 0x180012190: WriteFile → ReadFile (overlapped)
        ▼
SetupDi* + CreateFileW("…vid_3554&pid_XXXX&mi_01&colNN…") + WriteFile/ReadFile
```

- `FormMain.DeviceConnect` passa **o mesmo caminho de dispositivo** para entrada e
  saída (`UsbServer.Start(deviceString, deviceString, …)`). [E]
- `HidD_SetFeature` só é usado para pareamento e atualização (`CS_UsbFinder_*ByFeature`). [E]

## 3. Identificação do dispositivo

| Campo | Valor | Fonte |
|---|---|---|
| Vendor ID | `0x3554` | `Config.ini` `VID=TEFNWlUzNTU0` → `LAMZU3554` [E] |
| PID com fio | `0xF50F` | `M_PID` [E] |
| PIDs de receptor | `0xF50D`, `0xF510`, `0xF517` | `D_PID` [E]; `0xF510` = "LAMZU 4K Receiver" [H] |
| Interface | `1` | `Config.ini` `Interfaceid=1` [E] |
| Coleção | usage page `0xFF02`, usage `0x02` | única coleção que aceita o report `0x08` [H] |
| MCUs | mouse nRF52840, receptor CX52650N / CH32V305, sensor PAW3395 | `MM`, `DM`, `D4M`, `Sensor` [E] |

## 4. Formato do relatório

Um relatório de saída e um de entrada, ambos com **report ID `0x08` e 17 bytes**
(`WriteFile(h, entry+3, 0x11)` e `ReadFile(h, buf, 0x11)` em `0x18001264e`/`0x1800127da`). [E][H]

| Byte | Conteúdo |
|---|---|
| 0 | `0x08` (report ID) |
| 1 | comando |
| 2 | status (`0`) |
| 3–4 | endereço (big-endian) |
| 5 | comprimento (`≤ 10`; bit `0x80` só no modo teclado, `UsbServer_KeyboardStart`) |
| 6–15 | dados |
| 16 | checksum = `(0x55 − Σ bytes[0..15]) & 0xFF` (função `0x18000f060`) [E][H] |

Comportamento de transporte da thread nativa [E]: uma requisição por vez; ≥ 8 ms
entre escritas (`clock()` em `0x180012620`); até 5 tentativas; timeout de 1000 ms,
ou 5000 ms quando o comando é `0x09`. Uma resposta só é aceita se o checksum confere
e `byte[1]` é igual ao comando pendente; para `WRITE_FLASH` os 17 bytes precisam ser
um eco exato (`0x180011cb0`).

## 5. Comandos

Valores do enum `DriverLib.UsbCommandID` [E], conferidos contra os bytes que cada
`UsbServer_*` grava em `[rsp+0x43]` [E].

| Cmd | Nome | Observação |
|---|---|---|
| `0x01` | EncryptionData / ReadCIDMID | |
| `0x02` | PCDriverStatus | |
| `0x03` | DeviceOnLine | **respondido pelo receptor**; `data[0] ≠ 0` = mouse ligado [H] |
| `0x04` | BatteryLevel | `data = [nível %, carregando, mV_hi, mV_lo]` (`GetDeviceBatteryStatus`) [E][H] |
| `0x05`/`0x06` | DongleEnterPair / GetPairState | |
| `0x07` | WriteFlash | `[addr, len, dados]` |
| `0x08` | ReadFlash | `[addr, len]` → resposta com os dados em 6..15 [H] |
| `0x09` | ClearSetting | reset de fábrica, timeout 5 s |
| `0x0A` | StatusChanged | **não solicitado**; bitfield decodificado em `GetDeviceStatusChanged` |
| `0x0B`–`0x0D` | SetVidPid / SetDescriptorString / EnterUsbUpdateMode | perigosos, não expostos |
| `0x0E`/`0x0F` | Get/SetCurrentConfig (perfil) | |
| `0x11` | EnterMTKMode | não exposto |
| `0x12` | ReadVersionID | **repassado ao mouse**: sem resposta com o mouse dormindo [H] |
| `0x14`/`0x15` | Set/Get 4K dongle RGB | |
| `0x16`/`0x17` | Set/Get LongRangeMode | |

## 6. Mapa da flash de configuração (0x00–0xBF)

Dois esquemas de integridade, ambos aplicados pelo firmware:

- **par**: `[v, 0x55 − v]` para valores de 1 byte (`MouseConfigParser`, `0x180007060`)
- **bloco**: `[b0 … bn-1, 0x55 − Σ]` para registros de vários bytes

| Endereço | Formato | Campo (`DriverLib.*`) | Exemplo [H] |
|---|---|---|---|
| `0x00` | par | `reportRate`: 1=1000, 2=500, 4=250, 8=125, 0x10=2000, 0x20=4000 Hz | `01 54` |
| `0x02` | par | `maxDPI` (estágios ativos) | `01 54` |
| `0x04` | par | `currentDPI` (índice; o parser exige `< maxDPI`) | `00 55` |
| `0x06`/`0x08` | par | `xSpindown`/`ySpindown` (LOD) | |
| `0x0A` | par | `silenceHeight` | |
| `0x0C + 4i` | bloco 3 | DPI do estágio *i*: `[x, y, ex]` | `1f 1f 00 17` = 1600 |
| `0x2C + 4i` | bloco 3 | cor RGB do estágio *i* | `00 ff ff 57` |
| `0x4C`–`0x53` | 4 pares | `DPILed`: mode, brightness, breathSpeed, enable | |
| `0x54`–`0x5F` | ? | **desconhecido** (não lido pelo parser) | `ff 00 ff 57 …` |
| `0x60 + 4i` | bloco 3 | botão *i*: `KeyFunMap` `[type, param1, param2]` | `01 01 00 53` = esquerdo |
| `0xA0` | bloco 6 | `LedBar`: mode, R, G, B, speed, brightness | `01 ff 00 00 07 09 45` |
| `0xA7` | par | `LedBar.enable` | |
| `0xA9`…`0xB9` | pares | `keyDebounceTime`, `motionSyncEnable`, `allLedOffTime`, `linearCorrectionEnable`, `rippleControlEnable`, `moveOffLedEnable`, `sensorCustomSleepTimeEnable`, `sensorSleepTime`, `sensorPowerSavingModeEnable` | |
| `0xBB` | par | **desconhecido** (firmware mais novo que o app?) | `0a 4b` |
| `0x100 + 0x20k` | ver §8 | atalho de teclado do botão *k* | |
| `0x300 + 0x180k` | — | macro do botão *k* (`BufferToMacroKey`) — **não implementado** | |

Escritas: `ProtocolDataUpdate` (`0x1800079c0`) compara o struct novo com o antigo e
envia um `WRITE_FLASH` por campo alterado, com o campo inteiro incluindo o checksum
(pares com `len=2`, registros de DPI/botão com `len=4`); regiões maiores são fatiadas
em blocos de 10 bytes (`0x180007830`). [E]

## 7. Codificação do DPI (sensor 3395)

`DPIControl::ValueToDPI` / `DPIControl::UpdateUI` no IL [E]; `Config.ini` define
`DPIRange=50,26000,50,0x00`, então `Sensor.DPIex = 0` e o passo é 50:

```
raw = dpi / 50 − 1            hi = raw >> 8
x = y = raw & 0xFF            ex = (hi << 2) | (hi << 6)
decodificação: raw = x | ((ex >> 6) << 8);  dpi = (raw + 1) · 50
               (· 100 se ex & 0x22;  ×2 se ex & 0x11 — caminhos de outros sensores)
```

Verificado no hardware: `1f 1f 00` → 1600, `07 07 00` → 400, `7f 7f 00` → 6400. [H]

## 8. Botões e atalhos

`KeyFunMap.type` = `DriverLib.KEY_CLASS` [E]: 0 desativado · 1 mouse (`param1` =
máscara: 1 esq, 2 dir, 4 meio, 8 voltar, 0x10 avançar) · 2 DPI (1 ciclo, 2 +, 3 −) ·
3 scroll horizontal (1 esq, 2 dir) · 4 tiro rápido (`param1`, `param2` brutos) ·
5 atalho · 6 macro · 7 ciclo de taxa · 8 LED · 9 perfil · 10 trava de DPI.
Os setters de `KeyFunMapDriver` mostram quais parâmetros cada tipo usa. [E]

Atalho (`ShortcutKeyToBuffer`, `0x1800096b0`) [E]:

```
[n (2..6)] + n × [flag | tipo, code_lo, code_hi] + [checksum dos 1+3n bytes]
flag: 0x80 = tecla pressionada, 0x40 = solta
tipo (HID_CODE_TYPE): 0 modificador (máscara: Ctrl 1, Shift 2, Alt 4, Cmd/Win 8),
                      1 tecla (usage HID de teclado), 2 mídia (usage consumer)
```

A tabela `DriverLib.KeyboardCodes` confirma os valores (`LCtrl` tipo 0 valor 1;
`A` → 0x04; `Mute` tipo 2 valor 0xE2; `Play` tipo 2 valor 0xCD). [E]
A ordem "pressiona tudo, solta ao contrário" usada por `parse_shortcut` foi
confirmada com `Ctrl+C` [H].

## 8b. Semântica das opções (arquivo de idioma + handlers da UI)

`Language/0-English.xml` traz os rótulos e valores de cada opção, e os handlers
`_3In1::*`, `_2In1::*` e `FormMain::*` mostram em qual campo cada controle grava. [E]

| Controle oficial | Campo | Valores |
|---|---|---|
| LOD | `silenceHeight` (`0x0A`) | 3 = 0,7 mm · 1 = 1 mm · 2 = 2 mm |
| Mode Select | `sensorPowerSavingModeEnable` (`0xB9`) | 0 = LP · 1 = HP ("Corded" = 10 não é gravado) |
| Peak Performance | `sensorCustomSleepTimeEnable` + `sensorSleepTime` | duração em unidades de 10 s (3, 6, 12, 30, 60, 90) |
| Lights off after not moving | `allLedOffTime` (`0xAD`) | unidades de 10 s (1 … 240) |
| DPI Light Effects | `DPILed.enable` + `mode` | 0 desliga; 1 fixo; 2 piscando |
| DPI brightness (1–10) | `DPILed.brightness` | `16, 30, 60, 90, 128, 150, 180, 210, 230, 255` (`DPIIndexToBrightness`) |
| DPI speed | `DPILed.breathSpeed` | 1–5 |
| Lighting Mode | `LedBar.enable` + `mode` | 0 desligado · 1 arco-íris em movimento · 2 cor única · 3 arco-íris fixo · 4 neon · 5 arco-íris piscante · 6 multicolorido fixo |
| Light brightness / speed | `LedBar.brightness` / `speed` | 0–9 (exibidos 1–10) |
| Debounce | `keyDebounceTime` (`0xA9`) | 0–20 ms |

Funções de botão (`KeyFunction` / `SubKeyFunction`): tiro rápido `param1` =
intervalo 10–255 ms, `param2` = repetições 0–3 (0 = enquanto pressionado); trava de
DPI `param1 = dpi/50 − 1`; LED `param1` 0 = todas as luzes, 3 = faixa, 4 = alternar
efeitos; tipo `0x0B` = rolagem vertical (1 cima, 2 baixo); teclas de mídia usam o
mecanismo de atalho com usages consumer (`0xCD` play, `0xE9` volume +, …). [E]

## 8c. Identificação do modelo e diferenças entre modelos

`CS_UsbFinder_GetDeviceInfo` envia `EncryptionData` (`0x01`) com `len=8` e um
desafio aleatório de 4 bytes (`0x18000f160`); `GetDeviceInfo` (`0x180006fa0`) lê a
resposta em `payload[4..6]` = **CID, MID, DeviceType**. [E] No receptor de teste:
`CID=11` (`Config.ini CID=LAMZU11`), `MID=2` (Atlantis Mini), `DeviceType=1`. [H]

`DeviceType` (`Mouse_Drive_Beta.DeviceType`): 0 Wireless1K, 1 Wireless4K, 2 Wired1K,
3 Wired8K, 4 Wireless2K, 5 Wireless8K. [E]

O app oficial adapta a tela por modelo (`Config.ini` → `DeviceParam`) [E]:

| Campo | Uso (`_3In1::UpdateUI`, `FormMain::UpdateLightUI`) |
|---|---|
| `SensorUI[0]` | quantas taxas existem: 2000 Hz se > 4, 4000 se > 5, 8000 se > 6; também limitado pelo `DeviceType` |
| `SensorUI[1]` | taxa padrão; `[3]–[12]` padrões de LED de DPI, modo, LOD, desempenho máximo, ripple, ângulo, motion sync |
| `SensorUI[2]` | `0` esconde o painel de efeito do LED de DPI |
| `DisplayLight` | `0` esconde a seção de iluminação |

| MID | Modelo | Taxa máx. do mouse | LED de DPI | Iluminação |
|---|---|---|---|---|
| 1 | Atlantis OG V2 | 8000 | não | não |
| 2 | Atlantis Mini | 8000 | não | não |
| 3 | Thorn | 8000 | sim | não |
| 4 | Maya | 8000 | não | não |
| 5 | Paro | 4000 | não | não |
| 9 | Atlantis Nordic-R'lyeh | 4000 | não | não |

Códigos de taxa = `Tag` dos botões de rádio: 125 → 8, 250 → 4, 500 → 2, 1000 → 1,
2000 → 16, 4000 → 32, **8000 → 64**. Com cabo ou em ≥ 2000 Hz o seletor LP/HP vira
"Corded" e fica bloqueado (`UpdateModeSelect`). Todos os modelos usam o mesmo sensor
(3395), a mesma faixa de DPI (50–26000) e o mesmo layout de 6 botões. [E]

## 9. Em aberto

- Escrita na flash **verificada [H]** com `lamzu selftest`: o mouse devolve eco exato
  de cada `WRITE_FLASH`, DPI e atalho (escrita em vários blocos em `0x1E0`) persistem
  e são lidos de volta, e a restauração deixa `0x000–0x2FF` idêntica ao backup.
  **Efeito físico verificado [H]** no Windows: estágio ativo em 800 DPI deixou o
  cursor mais lento, e `shortcut 4 vol-up` fez o botão "avançar" subir o volume.
  Regiões de atalho sem uso ficam em `0xFF` (flash apagada). Atalho com modificador
  (`Ctrl+C` gravado pela GUI) também verificado: copia o texto selecionado, o que
  confirma a ordem "pressiona tudo, solta ao contrário".
- `xSpindown`/`ySpindown` (`0x06`/`0x08`): nenhum controle da UI oficial grava neles.
- Regiões `0x54–0x5F` e `0xBB`, formato das macros, comando `0x0A` além do bitfield.
- Só o Atlantis Mini com receptor 4K foi testado no hardware (Windows e macOS). Os
  outros modelos e o modo com cabo (`0xF50F`) seguem o app oficial, mas não foram
  verificados.
- Modelos lançados depois do Mouse Drive Beta 1.6.0.43 (outros PIDs/MIDs) podem
  usar outro protocolo.

## 10. Reproduzir

```sh
python -m venv venv && venv/bin/pip install capstone pefile dnfile dncil
python -I tools/re/extract_res.py "Mouse Drive Beta.exe" out/      # DLLs embutidas
python -I tools/re/dis.py out/hidusb.dll UsbServer_SetCurrentConfig  # assembly anotado
python -I tools/re/il.py "Mouse Drive Beta.exe" "DPIControl::ValueToDPI"
python -I tools/re/consts.py "Mouse Drive Beta.exe" DriverLib.UsbCommandID
```
