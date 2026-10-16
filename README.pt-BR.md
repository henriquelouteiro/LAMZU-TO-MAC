# lamzu-mac

[English](README.md) · **Português (Brasil)**

Configurador aberto para mouses LAMZU (Atlantis OG V2, Atlantis Mini, Thorn, Maya,
Paro, Atlantis Nordic) no macOS, que não tem app oficial. É um port do
"Mouse Drive Beta" 1.6.0.43 para Windows, feito por engenharia reversa; o protocolo
e as evidências estão em [docs/PROTOCOL.md](docs/PROTOCOL.md).

Funciona também em Windows e Linux, porque usa `hidapi`.

> Projeto independente, sem relação com a LAMZU. Use por sua conta e risco; antes de
> mudar muita coisa, exporte um backup (`lamzu dump -o backup.bin` ou pela interface).

## Compatibilidade

O app identifica o modelo (pelo comando de identificação do próprio mouse) e mostra só
as opções que o app oficial mostra para ele, inclusive as taxas de polling suportadas
pelo par mouse + receptor.

| Modelo | Status |
|---|---|
| Atlantis Mini + receptor 4K | testado no Windows e no macOS |
| Atlantis OG V2, Thorn, Maya, Paro, Atlantis Nordic-R'lyeh | suportados pelo app oficial 1.6.0.43, ainda não testados aqui |
| Modo com cabo (PID `0xF50F`), receptores 1K/2K/8K | previstos, ainda não testados |
| Outros PIDs com VID `0x3554` | aceitos só se o dispositivo se identificar como LAMZU (CID 11) |

Testou outro modelo? Abra uma issue com a saída de `lamzu info` e `lamzu selftest`.

## Instalação

Precisa de Python 3.10+.

### macOS

Instale o Python pelo python.org ou com `brew install python` e depois:

```sh
git clone https://github.com/henriquelouteiro/LAMZU-TO-MAC.git
cd LAMZU-TO-MAC
bash scripts/install-mac.sh
```

O script cria `.venv`, instala `hidapi` e `PySide6`, roda os testes e cria
**LAMZU Configurator** em `~/Applications` (também abre pelo Spotlight). Depois,
conecte o receptor e rode `source .venv/bin/activate && lamzu selftest` para validar a
comunicação. O app aponta para a pasta onde você rodou o script, então mantenha essa pasta.

O canal de configuração é uma coleção HID vendor-defined (`0xFF02`), e não teclado ou
mouse, então nenhuma permissão especial deve ser necessária. Se o macOS pedir
*Monitoramento de Entrada*, autorize o Terminal/Python em Ajustes do Sistema →
Privacidade e Segurança.

### Windows / Linux

```sh
git clone https://github.com/henriquelouteiro/LAMZU-TO-MAC.git
cd LAMZU-TO-MAC
python -m venv .venv
.venv\Scripts\activate            # Linux: source .venv/bin/activate
pip install -e ".[gui]"
lamzu-gui
```

No Windows, feche o "Mouse Drive Beta" oficial para os dois não disputarem o
dispositivo. No Linux, seu usuário precisa de acesso de leitura/escrita ao dispositivo
`hidraw` (regra udev).

## Interface gráfica

```sh
lamzu-gui                                         # ou: python -m lamzu_mac.gui
lamzu-gui --demo tests/fixtures/flash_f510.bin    # sem mouse, usando um dump da flash
```

Seções: **Desempenho** (polling e estágios de DPI com cor), **Botões** (diagrama
clicável: cliques, DPI, rolagem, teclas de mídia, atalhos de teclado, tiro rápido, trava
de DPI), **Iluminação** (só para modelos com LED), **Sensor** (Motion Sync, correção de
ângulo, controle de ripple, LOD, modo LP/HP, debounce) e **Dispositivo** (bateria, modo
longa distância, backup, autoteste, padrões de fábrica). As mudanças são gravadas na hora.

## Linha de comando

```sh
lamzu info                        # modelo, firmware, bateria, DPI, botões, ajustes
lamzu dpi 0 800 --color 00ff00    # estágio 0 = 800 DPI, LED verde
lamzu stages 3                    # 3 estágios de DPI ativos
lamzu active 1                    # estágio ativo
lamzu rate 4000                   # 125 … 8000 Hz, conforme o mouse e o receptor
lamzu button 4 dpi-up             # botões 0-5: esq, dir, meio, voltar, avançar, dpi
lamzu shortcut 3 cmd+c            # atalho de teclado ou tecla de mídia (mute, play, vol-up…)
lamzu settings                    # lista de ajustes avançados
lamzu set motion-sync 1
lamzu dump -o backup.bin          # cópia bruta da flash de configuração
lamzu selftest                    # teste reversível de leitura/gravação (rode primeiro)
lamzu reset --yes                 # restaura padrões de fábrica
```

Use `--dry-run` para ver os pacotes sem enviá-los, e `-v` para ver o tráfego HID. Com o
receptor sem fio, o mouse precisa estar acordado: o receptor responde ao status online,
mas leituras e gravações são repassadas ao mouse.

## Estrutura

```
lamzu_mac/protocol.py   codificação pura: relatórios, checksum, mapa da flash, DPI, botões, modelos
lamzu_mac/device.py     transporte hidapi (mesma temporização/retentativas do app original)
lamzu_mac/cli.py        linha de comando
lamzu_mac/gui/          interface PySide6 (HID numa thread separada; modo --demo)
tests/                  testes com dump real de um receptor 0xF510 (+ fluxos da interface)
tools/re/               scripts usados na engenharia reversa
```

```sh
python -m unittest discover -s tests -t .
```

## Licença

MIT. Veja [LICENSE](LICENSE).
