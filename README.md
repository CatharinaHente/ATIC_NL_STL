# ATIC_NL_STL
Google doc with plans and tasks: https://docs.google.com/document/d/1SPUImBu9edmfQrpcPbQhhJVsOzUMZwjDN1QapCT2SGQ/edit?usp=sharing
Overleaf with edited report: https://www.overleaf.com/project/69f0cc0f5d2fdeb0479d7382
Sources:

ClarifySTL code is taken from: https://zenodo.org/records/17561877

LLAMA for Clarify here: https://huggingface.co/meta-llama/Meta-Llama-3-8B

DeepSTL code is taken from: https://github.com/JieHE-2020/DeepSTL

# PROJECT EXTENSION
1 - rule-based back translation (produce rule-based, human readable STL formula for human exception)
2 - automaton-based equivalence checks (are two representations equivalent)
(bonus - semantic slots)

1
STL formula --> syntax tree --> recursive traversal --> human readable text + structural trace
Parser: 

2
| Extension                       | Input                      | Technique                                              | Goal                                                                |
| ------------------------------- | -------------------------- | ------------------------------------------------------ | ------------------------------------------------------------------- |
| **Rule-based back-translation** | STL                        | STL → syntax tree → recursive traversal                | Human-readable text + structural trace for human exception handling |
| **Automaton-based equivalence** | Two STL representations    | STLSat directly; fallback to STL → LTL/LTLf → automata | Formal equivalence check                                            |
| **Bonus: semantic slots**       | NL + STL                   | Extract predicates, operators, intervals, relations    | Structured semantic comparison                                      |
| **Existing approaches**         |                            |                                                        |                                                                     |
| STLSat                          | Bounded, discrete-time STL | Tableau + FOL/SMT                                      | Equivalence                                                         |
| Spot                            | LTL                        | Automata                                               | Equivalence                                                         |
| LTLf2DFA                        | LTLf                       | DFA construction                                       | Equivalence via DFA                                                 |

STLSat — https://arxiv.org/abs/2607.21081
STLSat repository — https://github.com/MarcoZamponi/STLSat
PyTeLo — https://github.com/erl-lehigh/PyTeLo
PyTeLo paper — https://arxiv.org/abs/2310.08714
Spot — https://spot.lre.epita.fr/
Spot repository — https://gitlab.lre.epita.fr/spot/spot
LTLf2DFA — https://github.com/whitemech/LTLf2DFA
LTLf2DFA paper/software record — https://doi.org/10.5281/zenodo.3888410
