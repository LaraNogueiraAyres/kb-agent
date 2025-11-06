# Sistema Baseado em Conhecimento (SBC) Genérico

## Visão Geral do Projeto

Este projeto implementa um **Sistema Baseado em Conhecimento (SBC)** genérico e interativo em Python, completo com um motor de inferência (Forward e Backward Chaining), um *parser* de regras em Português e um sistema de explanação ("Por Quê?" e "Como?").

A aplicação é modular e flexível, permitindo que o usuário construa e teste diferentes bases de conhecimento (KB) através de um menu de linha de comando.

## Funcionalidades Principais

* **Motor de Inferência:** Suporte completo para Encandeamento para Frente (`forward_chain`) e Encandeamento para Trás (`backward_prove`).
* **Parser em PT-BR:** Interpretação de regras no formato `SE Condição E Condição ENTÃO Conclusão`.
* **Explanação:** Recursos "Por Quê?" e "Como?" que rastreiam a cadeia de raciocínio lógico (justificativas) utilizada para inferir um fato.
* **Gestão da KB:** Adição/remoção de regras e fatos, com catálogo automático de variáveis.
* **Interface Interativa:** Menu de comandos numérico/alias (`af`, `ar`, `fw`, `bk`) e *pickers* inteligentes.
* **Persistência:** Salva/Carrega a KB em formato JSON e importa regras em lote via TXT.

## Aplicações Implementadas

A flexibilidade do SBC foi demonstrada com a implementação de três bases de conhecimento distintas:

1.  ** Decisão Gerencial (Problema do Gerente):** Regras voltadas para a atribuição de tarefas, simulando um sistema que decide a elegibilidade ou o perfil de risco de um indivíduo com base em atributos como `Emprego`, `Idade`, `Renda` e `Dívida`.
2.  ** Diagnóstico Médico:** Regras que, a partir de dados clínicos (como `Febre`, `Dor_Articulacoes`, `Tosse`), inferem um diagnóstico ou grau de gravidade.
3.  ** "Mini"-Akinator:** Uma base de conhecimento que utiliza inferência  para adivinhar o objeto, animal ou personagem que o usuário está pensando, fazendo perguntas sequenciais.

## Como Rodar o Projeto
1. No terminal, execute: 
```bash
python3 kb_agent_menu.py
```
2. Assim que o programa iniciar, você verá o menu principal:
```
    1. adicionar fato       [af] - Adicionar fato escolhendo variável do catálogo (apenas variáveis de CONDIÇÃO)
    2. adicionar regra      [ar] - Adicionar regra (SE ... ENTÃO ...)
    3. listar fatos         [lf] - Listar fatos
    4. listar regras        [lr] - Listar regras
    5. listar variáveis     [lv] - Listar variáveis derivadas das regras
    6. remover fato         [rf] - Remover fato por atributo
    7. remover regra        [rr] - Remover regra por ID
    8. inferir forward      [fw] - Encadeamento para frente
    9. provar               [bk] - Provar objetivo (picker de variável-alvo e valor)
    10. por que              [pq] - Explanação: Por quê?
    11. salvar               [sv] - Salvar Base de Conhecimento (formato .json)
    12. carregar             [ld] - Carregar Base de Conhecimento (formato: .json)
    13. importar regras .txt [rt] - Importar regras de um arquivo .txt (SE ... ENTÃO ...)
    14. desfazer             [sd] - Desfazer última operação
    15. ajuda                [h] - Mostrar ajuda de todos os comandos
    16. sair                 [q] - Sair
```

3. Adicione uma regra manualmente (2), importe um conjunto de regras por txt (13) ou importe uma das bases disponíveis no repositório (12).


### Pré-requisitos

O projeto requer apenas o Python 3.x e suas bibliotecas padrão.

```bash
python3 --version
# Deve retornar algo como Python 3.x.x