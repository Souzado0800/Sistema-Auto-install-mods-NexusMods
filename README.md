# 🚗💨 AutoInstallModMySummerCar

<p align="center">
  <img src="https://img.shields.io/badge/Status-Release%20Ready-brightgreen?style=for-the-badge" alt="Status">
  <img src="https://img.shields.io/badge/My%20Summer%20Car-MSCLoader-blue?style=for-the-badge" alt="MSCLoader">
  <img src="https://img.shields.io/badge/Nexus%20Mods-Official%20API-orange?style=for-the-badge" alt="Nexus Mods">
  <img src="https://img.shields.io/badge/Plataforma-Linux%20%7C%20Zorin%20OS%20%7C%20Proton-purple?style=for-the-badge" alt="Linux">
  <img src="https://img.shields.io/badge/Suporte-ZIP%20%7C%20RAR5%20%7C%207Z-yellow?style=for-the-badge" alt="Formatos">
</p>

<h3 align="center">
  O instalador de mods 100% autônomo para My Summer Car.
</h3>

<p align="center">
  <b>Abra as páginas dos mods no seu navegador. Execute o programa. Ele faz todo o resto sozinho.</b>
</p>

---

## 🌟 O que este programa faz? (Explicação Simples)

Se você já tentou instalar mods do **Nexus Mods** para o **My Summer Car**, sabe o trabalho que dá:
1. Abrir cada mod;
2. Clicar em *Manual Download*;
3. Clicar em *Slow Download*;
4. Esperar o contador de 5 segundos;
5. Escolher a pasta onde salvar;
6. Abrir o arquivo compactado (`.zip`, `.rar` ou `.7z`);
7. Copiar as DLLs para a pasta `Mods` e as texturas para `Mods/Assets`...

O **AutoInstallModMySummerCar** elimina **tudo isso**.

### 🪄 Como funciona a experiência:
```text
 1. Você abre as abas dos mods desejados no seu navegador (Brave ou Chrome)
                                ↓
 2. Você dá dois cliques no programa (ou roda ./AutoInstallModMySummerCar)
                                ↓
 3. O programa descobre os mods das abas abertas sozinho
                                ↓
 4. Clica em "Manual Download" e "Slow Download" automaticamente
                                ↓
 5. Espera os 5 segundos oficiais do Nexus e baixa os arquivos
                                ↓
 6. FECHA a aba do mod no navegador assim que o download termina
                                ↓
 7. Extrai e instala tudo na pasta correta do My Summer Car (/Mods)
                                ↓
                       ✓ PRONTO PARA JOGAR!
```

---

## ✨ Principais Vantagens

* 🌐 **Detecção Automática de Abas**: Você não precisa copiar nenhum link. Basta deixar a página do mod aberta no Brave ou Chrome.
* 🖱️ **Download 100% Automático**: Localiza e clica nos botões oficiais de download, inclusive em interfaces modernas com Shadow DOM.
* 🚫 **Sem Janelas Chatinhas**: O programa impede a abertura da janela do sistema perguntando "Salvar como...". O download vai direto para o lugar certo sem exigir que você aperte Enter.
* 🚪 **Fecha Abas Sozinho**: Cada aba baixada é fechada no seu navegador na mesma hora, mantendo sua área de trabalho limpa.
* 📦 **Aceita Qualquer Formato**: Extrai nativamente arquivos `.zip`, `.7z` e formatos modernos `.rar` (RAR5).
* 🛡️ **Proteção Antiestrago (Safe Mode)**: Arquivos que você já tinha instalado antes (como o próprio MSCLoader) ficam blindados como `UNMANAGED` e nunca são apagados ou corrompidos.
* 🧠 **Detector de Dependências**: Identifica requisitos obrigatórios e organiza a ordem de instalação perfeitamente.
* ⚡ **Super Rápido (Idempotente)**: Se você rodar o programa e os mods já estiverem instalados, ele avisa em menos de 1 segundo: *"Nothing to do"*, sem baixar nada repetido.
* 🔒 **Seguro e Oficial**: Não burla regras do Nexus Mods nem pede sua senha. Suporta contas Free e Supporter de forma 100% legal.

---

## 🚀 Como Usar

### 📋 Requisitos
* **Linux** (Zorin OS, Ubuntu, Debian, Pop!_OS, etc.)
* **Navegador**: Brave ou Google Chrome / Chromium
* **Python 3.10+** (já vem instalado na maioria das distribuições Linux)

---

### Passo 1: Obter o Projeto
```bash
git clone https://github.com/Souzado0800/Sistema-Auto-install-mods-NexusMods.git
cd Sistema-Auto-install-mods-NexusMods
```

### Passo 2: Primeira Execução (Onboarding Simples)
Na primeira vez que você abrir o programa:
```bash
./AutoInstallModMySummerCar
```
1. Ele abrirá automaticamente a página oficial de chaves do Nexus Mods no seu navegador (`https://www.nexusmods.com/users/myaccount?tab=api`).
2. Role até o fim da página em **Personal API Key**, clique em **Generate** e copie a sua chave.
3. Cole a chave na janela segura do programa. Ela será criptografada e guardada no seu computador. Você **nunca mais** precisará digitar de novo.

---

### Passo 3: Uso no Dia a Dia
Sempre que quiser instalar mods novos:

1. Abra o **Brave** ou **Chrome** e navegue pelas páginas dos mods que quiser no Nexus Mods.
2. Deixe as abas abertas.
3. Execute o programa:
   * **Pelo Menu de Aplicativos**: Procure por **AutoInstallModMySummerCar** e clique nele;
   * **Ou pelo Terminal**:
     ```bash
     ./AutoInstallModMySummerCar
     ```
4. Veja a mágica acontecer: o terminal mostrará o nome real dos mods, fará o download, fechará as abas e instalará tudo no jogo!

---

## 📊 Exemplo do que Você Vê na Tela

```text
╭──────────────────────────────────────────────────────────────────────────────╮
│                          NEXUS MODS AUTO INSTALLER                           │
│       High-Performance · Safe · Dependency-Aware · Official Compliant        │
╰──────────────────────────────────────────────────────────────────────────────╯
✓ Nexus authenticated: Matheushopi (SUPPORTER)
✓ My Summer Car detected
✓ MSCLoader detected
✓ Mods directory: /home/souza/My Summer Car/Mods
✓ Local scan: 3 files (1 managed, 2 unmanaged)

Detecting browser...
✓ Brave
Scanning Nexus tabs...

                         MODS DETECTED                         
┏━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┓
┃ #    ┃ Mod Name           ┃ Nexus ID   ┃ Origin             ┃
┡━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━┩
│ 1    │ Lights On Switches │ 868        │ ACTIVE_SESSION     │
│ 2    │ New Lights         │ 6683       │ ACTIVE_SESSION     │
└──────┴────────────────────┴────────────┴────────────────────┘

2 Nexus tabs / links
2 unique mods

Resolving dependencies...
Downloading...
✓ Botão 'Slow Download' acionado automaticamente via CDP.
Aguardando contador oficial do Nexus (5s)...
✓ Aba do Mod #868 fechada automaticamente no navegador.
✓ Botão 'Slow Download' acionado automaticamente via CDP.
Aguardando contador oficial do Nexus (5s)...
✓ Aba do Mod #6683 fechada automaticamente no navegador.

Installing...
═══ POST-INSTALL FILESYSTEM DIFF ═══
 Files added ............... 2
   + LightsOnSwitches.dll (53248 bytes)
   + NewLights.dll (41984 bytes)
 Files modified ............ 0
 Files removed ............. 0

✓ COMPLETE
Finished in 14.82s
```

---

## ❓ Perguntas Frequentes (FAQ)

#### 1. Preciso pagar o Nexus Mods Premium?
**Não!** O programa foi construído sob medida para contas gratuitas (**Free** e **Supporter**). Ele automatiza a interação normal de clique e respeita o contador oficial de 5 segundos. Se você tiver Premium, ele baixa ainda mais rápido via CDN direta.

#### 2. E se o mod vier em formato `.rar`?
Funciona perfeitamente. O projeto vem acompanhado de um motor interno `7zz` que descompacta qualquer versão moderna de arquivos compactados (inclusive RAR5), sem exigir que você instale programas extras.

#### 3. Ele pode apagar meus mods antigos ou meu save?
**Nunca.** O sistema possui uma camada de segurança chamada `UNMANAGED`. Todo arquivo que já existia na pasta do jogo antes de o programa rodar é tratado como intocável.

#### 4. Onde os mods são instalados?
O programa detecta automaticamente sua instalação do jogo (Steam nativa, Proton ou Flatpak). Por padrão no Linux:
```text
/home/seu_usuario/My Summer Car/Mods
```

---

## 🛠️ Tecnologias Utilizadas

* **Python 3.12** com `asyncio` para operações paralelas ultra-rápidas.
* **Chromium DevTools Protocol (CDP)** nativo via WebSockets para automação limpa sem extensões externas.
* **SQLite** local para histórico de instalações, hashes SHA-256 e idempotência.
* **Rich** para interface moderna e intuitiva no terminal.

---

## 📄 Licença

Este projeto é disponibilizado sob a licença **MIT**. Sinta-se livre para usar, estudar e compartilhar.
