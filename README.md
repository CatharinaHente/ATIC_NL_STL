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
existing approaches    input                         technique                equivalence
STLSat                 bounded, discrete-time STL    tableau + FOL/SMT        yes
SPOT                   LTL                           automata                 yes
LTL2DFA                LTLf                          DFA construction         yes (via DFA)

pre-step to SPOT/LTL2DFA
STL->LTL/LTLf          restricted STL                reduction, then automata

idea: use STLSat directly if it works, revert to LTL/automata reduction if it does not 
      (our contribution: streamlined pipeline)
