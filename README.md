# 🤖 Sistema Baseado em Conhecimento (SBC) Genérico

## 🚀 Visão Geral do Projeto

Este projeto implementa um **Sistema Baseado em Conhecimento (SBC)** genérico e interativo em Python, completo com um motor de inferência (Forward e Backward Chaining), um *parser* de regras em Português e um sistema de explanação ("Por Quê?" e "Como?").

A aplicação é modular e flexível, permitindo que o usuário construa e teste diferentes bases de conhecimento (KB) através de um menu de linha de comando.

## ✨ Funcionalidades Principais

* **Motor de Inferência:** Suporte completo para Encandeamento para Frente (`forward_chain`) e Encandeamento para Trás (`backward_prove`).
* **Parser em PT-BR:** Interpretação de regras no formato `SE Condição E Condição ENTÃO Conclusão`.
* **Explanação:** Recursos "Por Quê?" e "Como?" que rastreiam a cadeia de raciocínio lógico (justificativas) utilizada para inferir um fato.
* **Gestão da KB:** Adição/remoção de regras e fatos, com catálogo automático de variáveis.
* **Interface Interativa:** Menu de comandos numérico/alias (`af`, `ar`, `fw`, `bk`) e *pickers* inteligentes.
* **Persistência:** Salva/Carrega a KB em formato JSON e importa regras em lote via TXT.

## 🎯 Aplicações Implementadas

A flexibilidade do SBC foi demonstrada com a implementação de três bases de conhecimento distintas:

1.  **💼 Decisão Gerencial (Problema do Gerente):** Regras voltadas para a atribuição de tarefas, simulando um sistema que decide a elegibilidade ou o perfil de risco de um indivíduo com base em atributos como `Emprego`, `Idade`, `Renda` e `Dívida`.
2.  **🩺 Diagnóstico Médico:** Regras que, a partir de dados clínicos (como `Febre`, `Dor_Articulacoes`, `Tosse`), inferem um diagnóstico ou grau de gravidade.
3.  **🔮 "Mini"-Akinator:** Uma base de conhecimento que utiliza inferência  para adivinhar o objeto, animal ou personagem que o usuário está pensando, fazendo perguntas sequenciais.

## ⚙️ Como Rodar o Projeto

### Pré-requisitos

O projeto requer apenas o Python 3.x e suas bibliotecas padrão.

```bash
python3 --version
# Deve retornar algo como Python 3.x.x