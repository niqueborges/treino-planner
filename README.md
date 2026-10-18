```markdown
# Treino Planner

Aplicação web para criação, organização e execução de planos de treino.

O Treino Planner permite cadastrar usuários, montar uma programação semanal de exercícios, definir séries, repetições, carga e descanso e executar os treinos pelo navegador.

A aplicação utiliza uma biblioteca de mídias para apresentar os exercícios durante o treino. Essa biblioteca pode ser configurada para utilizar uma pasta de mídias existente no computador.

## Requisitos

- Windows 10/11
- WSL2
- Ubuntu no WSL
- Python 3
- Git
- Navegador web

Para utilizar a aplicação em outros dispositivos da mesma rede, como celular ou tablet, eles precisam estar conectados à mesma rede local do computador que executa o servidor.

## Clonar o projeto

No WSL:

```bash
cd ~/projetos
git clone https://github.com/niqueborges/treino-planner.git
cd treino-planner
```

Entre na branch principal:

```bash
git checkout Main
```

## Biblioteca de mídias

O Treino Planner utiliza uma pasta externa como fonte das mídias dos exercícios.

A pasta pode estar em qualquer local acessível pelo WSL.

Exemplo no Windows:

```text
D:\Dados\TreinoPlanner\dataset-original
```

O mesmo caminho dentro do WSL será:

```text
/mnt/d/Dados/TreinoPlanner/dataset-original
```

A aplicação utiliza a variável de ambiente:

```bash
TREINO_PLANNER_DATASET_ROOT
```

Para definir a biblioteca de mídias:

```bash
export TREINO_PLANNER_DATASET_ROOT=/mnt/d/Dados/TreinoPlanner/dataset-original
```

Por exemplo:

```bash
cd ~/projetos/treino-planner

export TREINO_PLANNER_DATASET_ROOT=/mnt/d/Dados/TreinoPlanner/dataset-original
```

A variável precisa estar definida no mesmo ambiente em que o servidor será iniciado.

### Estrutura da biblioteca

A biblioteca atualmente utilizada pelo projeto possui uma estrutura semelhante a:

```text
dataset-original/
└── GIFS PLANEJADOR - ORGANIZADOS/
    ├── FEMININO/
    │   ├── ...
    │   └── ...
    └── MASCULINO/
        ├── ...
        └── ...
```

A aplicação resolve as mídias a partir das informações cadastradas no catálogo e dos caminhos existentes na biblioteca.

Portanto, não é necessário copiar a biblioteca de mídias para dentro do repositório Git.

Isso também permite que cada instalação utilize sua própria biblioteca.

## Usando outra biblioteca de mídias

É possível apontar o Treino Planner para outra pasta de mídias:

```bash
export TREINO_PLANNER_DATASET_ROOT=/caminho/para/sua/biblioteca
```

No Windows, por exemplo:

```bash
export TREINO_PLANNER_DATASET_ROOT=/mnt/c/Users/seu-usuario/MeusExercicios
```

A biblioteca utilizada precisa ser compatível com o catálogo e com a estrutura esperada pela aplicação.

Importante: atualmente o sistema não transforma automaticamente qualquer GIF colocado em uma pasta em um novo exercício.

Ou seja, não basta criar:

```text
MeusExercicios/
├── agachamento.gif
├── flexao.gif
└── corrida.gif
```

e esperar que os três exercícios sejam automaticamente cadastrados.

A mídia precisa estar associada aos exercícios existentes no catálogo ou passar pelo processo de importação suportado pela aplicação.

## Formatos de mídia

O fluxo atualmente validado do projeto utiliza principalmente GIFs.

O sistema não deve ser considerado, neste momento, um gerenciador genérico de qualquer tipo de mídia.

Não há garantia de funcionamento para:

- JPG
- JPEG
- PNG
- WebP
- MP4
- WebM
- outros formatos de vídeo

Suporte completo a imagens estáticas ou vídeos exigiria alterações na aplicação e validação específica.

## Iniciar a aplicação

Com o projeto configurado:

```bash
cd ~/projetos/treino-planner
```

Defina a biblioteca de mídias:

```bash
export TREINO_PLANNER_DATASET_ROOT=/mnt/d/Dados/TreinoPlanner/dataset-original
```

Inicie o servidor:

```bash
python3 -m app.cli serve --host 0.0.0.0 --port 8000
```

A aplicação ficará disponível em:

```text
http://localhost:8000
```

## Acessar pelo celular ou tablet

O servidor utiliza:

```text
--host 0.0.0.0
```

Isso permite que outros dispositivos da mesma rede local acessem a aplicação.

No computador que executa o WSL, descubra o endereço IP da máquina:

```bash
hostname -I
```

Por exemplo:

```text
192.168.0.100
```

No celular ou tablet, abra:

```text
http://192.168.0.100:8000
```

Substitua o endereço pelo IP apresentado no seu computador.

O computador e o dispositivo móvel precisam estar na mesma rede.

## Criar um usuário

Ao acessar a aplicação, cadastre o usuário que utilizará o planejador.

Os dados ficam armazenados localmente no banco de dados da instalação.

## Criar um plano de treino

Depois de criar o usuário:

1. Acesse o planejador.
2. Selecione o usuário.
3. Escolha os exercícios.
4. Organize os exercícios na programação semanal.
5. Configure séries e repetições.
6. Informe a carga quando aplicável.
7. Defina o tempo de descanso.
8. Salve o plano.

## Executar um treino

Durante a execução do treino, a aplicação apresenta os exercícios cadastrados e suas respectivas mídias.

O fluxo permite acompanhar as séries e utilizar o cronômetro de descanso entre elas.

O treino pode ser acessado pelo navegador do computador ou por outro dispositivo da rede local.

## Banco de dados

O Treino Planner utiliza SQLite para armazenar os dados da aplicação.

O banco pertence à instalação local do servidor.

Por isso, o repositório Git não deve ser utilizado como mecanismo de sincronização do banco de dados entre dispositivos.

Para fazer backup, copie o arquivo de banco utilizado pela instalação.

Antes de copiar o banco, recomenda-se parar o servidor para evitar copiar o arquivo durante uma operação de escrita.

## Importação de dataset

O projeto possui um comando para importação da biblioteca de exercícios.

Exemplo:

```bash
python3 -m app.cli import-dataset /caminho/para/dataset
```

Também é possível utilizar um arquivo ZIP quando esse for o formato disponível:

```bash
python3 -m app.cli import-dataset /caminho/para/dataset.zip
```

A importação mantém as informações necessárias para relacionar os exercícios às mídias disponíveis.

O processo é incremental e pode preservar a origem das mídias importadas.

## Executar os testes

Os testes Python podem ser executados com:

```bash
python3 -m pytest
```

Os testes JavaScript podem ser executados com:

```bash
npm test
```

Os comandos podem variar conforme o ambiente e a configuração local do projeto.

## Windows + WSL2

O servidor pode ser executado diretamente pelo WSL.

Uma alternativa conveniente no Windows é criar um atalho para:

```text
C:\Windows\System32\wsl.exe
```

O atalho pode iniciar o projeto diretamente no WSL.

Um exemplo conceitual é:

```text
wsl.exe bash -lc "cd /home/nique/projetos/treino-planner && export TREINO_PLANNER_DATASET_ROOT=/mnt/d/Dados/TreinoPlanner/dataset-original && python3 -m app.cli serve --host 0.0.0.0 --port 8000"
```

O caminho deve ser adaptado para a instalação de cada usuário.

Não é necessário desativar o Smart App Control do Windows para utilizar o projeto.

## Limitações atuais

O Treino Planner está em desenvolvimento. Algumas limitações são importantes antes de utilizar o projeto como uma aplicação pronta para produção.

### Biblioteca de exercícios

O catálogo atual depende dos dados disponíveis na biblioteca importada.

Os nomes dos exercícios podem refletir o dataset de origem e podem conter diferenças de idioma, nomenclatura ou variações do mesmo exercício.

A busca depende principalmente dos nomes cadastrados.

Ainda não existe uma camada completa de aliases, sinônimos e traduções para consolidar automaticamente termos equivalentes.

Por exemplo, exercícios semelhantes podem aparecer separadamente quando possuem nomes diferentes no catálogo.

### Exercícios semelhantes

O catálogo pode conter variações do mesmo exercício.

Diferenças como:

- gênero;
- nomenclatura;
- variação do exercício;
- origem da mídia;

podem resultar em registros separados.

Ainda não existe uma consolidação completa dessas variações em uma identidade única de exercício.

### Tipos de exercício

O modelo atual é mais adequado para exercícios estruturados em:

- séries;
- repetições;
- carga;
- unidade;
- descanso.

Modalidades como caminhada, corrida, bicicleta ou outros exercícios predominantemente cardiovasculares podem exigir informações diferentes, como:

- duração;
- distância;
- velocidade;
- ritmo;
- inclinação.

Esses casos ainda não estão representados de forma tão específica quanto os exercícios tradicionais de força.

### Mídias

A implementação atual foi validada principalmente com GIFs.

Não existe atualmente uma camada genérica e validada para utilizar imagens estáticas ou vídeos como substitutos das mídias atuais.

### Biblioteca não é distribuída junto com o projeto

A biblioteca de mídias não faz parte do repositório Git.

Isso evita colocar uma grande quantidade de arquivos binários no repositório e também evita distribuir conteúdo cuja licença possa não permitir redistribuição.

Cada usuário deve fornecer sua própria biblioteca de mídias.

### Licenciamento das mídias

O código do Treino Planner e os arquivos de mídia são coisas diferentes.

O usuário é responsável por verificar se possui autorização para utilizar, modificar ou redistribuir as mídias utilizadas na sua instalação.

Não presuma que uma mídia encontrada na internet pode ser redistribuída livremente.

### Banco de dados local

O banco de dados pertence à instalação local.

O projeto não possui atualmente sincronização automática do banco com a nuvem.

Também não existe sincronização automática entre diferentes instalações do Treino Planner.

### Autenticação

A aplicação atualmente não deve ser considerada um sistema com autenticação completa de usuários.

Não utilize a aplicação exposta diretamente à internet como se fosse um serviço público pronto para produção.

O uso recomendado atualmente é em ambiente local ou rede privada.

### Funcionamento offline

A aplicação possui recursos de aplicação web progressiva, mas isso não significa que todo o sistema funcione offline.

O banco de dados e a API continuam dependendo do servidor local.

A instalação não deve ser considerada uma aplicação totalmente offline no sentido de não depender do servidor.

## Segurança

O servidor foi projetado principalmente para utilização local.

Se o projeto for disponibilizado para uma rede maior ou para a internet, será necessário implementar medidas adicionais de segurança, como:

- autenticação adequada;
- autorização;
- proteção de dados;
- configuração segura de rede;
- HTTPS;
- gerenciamento de credenciais;
- políticas de acesso;
- proteção contra ataques à aplicação.

Não exponha diretamente uma instalação de desenvolvimento à internet.

## Estrutura geral

O projeto possui, entre outras partes:

```text
treino-planner/
├── app/
├── tests/
├── docs/
├── data/
├── package.json
├── README.md
└── ...
```

A estrutura pode mudar conforme o desenvolvimento do projeto.

## Contribuição

Sugestões, correções e melhorias são bem-vindas.

Antes de alterar o projeto, consulte a documentação existente e execute os testes disponíveis.

## Status

Projeto em desenvolvimento.

O objetivo atual é disponibilizar um planejador de treinos funcional, local e acessível pelo navegador, mantendo a biblioteca de exercícios separada do código da aplicação.
```