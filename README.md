# lamzu-mac

Configurador aberto para mouses LAMZU (Atlantis OG V2, Atlantis Mini, Thorn, Maya,
Paro, Atlantis Nordic) em macOS, que não tem app oficial. É um port do
"Mouse Drive Beta" 1.6.0.43 para Windows, feito por engenharia reversa; o protocolo
e as evidências estão em [docs/PROTOCOL.md](docs/PROTOCOL.md).

Funciona também em Windows e Linux, porque usa `hidapi`.

> Projeto independente, sem relação com a LAMZU. Use por sua conta e risco; antes de
> mudar muita coisa, exporte um backup (`lamzu dump -o backup.bin` ou pela interface).

## Compatibilidade

O app detecta o modelo (comando de identificação do próprio mouse) e mostra só as
opções que o app oficial mostra para ele, inclusive as taxas de polling suportadas
pelo par mouse + receptor.

| Modelo | Status |
|---|---|
| Atlantis Mini + receptor 4K | testado no Windows e no macOS |
| Atlantis OG V2, Thorn, Maya, Paro, Atlantis Nordic-R'lyeh | suportados pelo app oficial 1.6.0.43, ainda não testados aqui |
| Modo com cabo (PID `0xF50F`), receptores 1K/2K/8K | previstos, ainda não testados |
| Outros PIDs com VID `0x3554` | aceitos só se o dispositivo se identificar como LAMZU (CID 11) |

Testou outro modelo? Abra uma issue com a saída de `lamzu info` e `lamzu selftest`.

## Instalação (macOS)

Precisa de Python 3.10+ (python.org ou `brew install python`). Na pasta do projeto:

```sh
bash scripts/install-mac.sh
```

O script cria `.venv`, instala `hidapi` e `PySide6`, roda os testes e cria
**LAMZU Configurator** em `~/Applications`. Depois, conecte o receptor e rode
`source .venv/bin/activate && lamzu selftest` para validar a comunicação.

Instalação manual: `python3 -m pip install ".[gui]"`.

O canal de configuração é uma coleção HID vendor-defined (`0xFF02`), e não teclado
ou mouse; por isso não deve precisar da permissão de *Monitoramento de Entrada*.
Isso ainda não foi verificado num Mac.

## Interface gráfica

```sh
python3 -m pip install ".[gui]"     # inclui PySide6 (Qt)
lamzu-gui                           # ou: python3 -m lamzu_mac.gui
lamzu-gui --demo tests/fixtures/flash_f510.bin   # sem mouse, usando um dump
```

Cinco seções: **Desempenho** (polling e estágios de DPI com cor), **Botões**
(diagrama clicável; clique, DPI, rolagem, mídia, atalho de teclado, tiro rápido,
trava de DPI), **Iluminação**, **Sensor** (Motion Sync, correção de ângulo,
ripple, LOD, modo LP/HP, debounce) e **Dispositivo** (bateria, longa distância,
backup, autoteste, padrões de fábrica). As mudanças são gravadas na hora.

## Linha de comando

```sh
lamzu info                        # firmware, bateria, DPI, botões, ajustes
lamzu dpi 0 800 --color 00ff00    # estágio 0 = 800 DPI, LED verde
lamzu stages 3                    # 3 estágios de DPI ativos
lamzu active 1                    # estágio ativo
lamzu rate 4000                   # 125/250/500/1000/2000/4000 Hz
lamzu button 4 dpi-up             # botões 0-5: esq, dir, meio, voltar, avançar, dpi
lamzu shortcut 3 cmd+c            # atalho de teclado ou mídia (mute, play, vol-up…)
lamzu settings                    # ajustes avançados disponíveis
lamzu set motion-sync 1
lamzu dump -o backup.bin          # cópia bruta da flash de configuração
lamzu selftest                    # teste reversível de leitura/gravação (rode primeiro no Mac)
lamzu reset --yes                 # restaura padrões de fábrica
```

Antes de gravar, use `--dry-run` para ver os pacotes sem enviá-los, e `-v` para ver
o tráfego HID. Com o receptor sem fio, o mouse precisa estar acordado: o receptor
responde ao status online, mas leituras e gravações são repassadas ao mouse.

Feche o "Mouse Drive Beta" ao usar no Windows, para os dois não disputarem o canal.

## Estrutura

```
lamzu_mac/protocol.py   codificação pura: relatórios, checksum, mapa da flash, DPI, botões
lamzu_mac/device.py     transporte hidapi (mesma temporização/retentativas do app original)
lamzu_mac/cli.py        linha de comando
lamzu_mac/gui/          interface PySide6 (HID numa thread separada; modo --demo)
tests/                  testes com dump real de um receptor 0xF510 (+ fluxo da GUI)
tools/re/               scripts usados na engenharia reversa
```

```sh
python -m unittest discover -s tests -t .
```

## Licença

MIT. Veja [LICENSE](LICENSE).
