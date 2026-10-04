## STLSat setup
1. Install Rust: https://rustup.rs/
2. brew install z3
3. export Z3_SYS_Z3_HEADER=$(brew --prefix z3)/include/z3.h
4. export LIBRARY_PATH=$(brew --prefix z3)/lib:$LIBRARY_PATH
5. git clone https://github.com/ZamponiMarco/stlsat.git && cd stlsat && cargo install --path 

## STLSat formula syntax:
Temporal: G[a,b] φ, F[a,b] φ, φ U[a,b] ψ, φ R[a,b] ψ
Boolean: &&, ||, !, ->, <->
Atoms: x > 5.0, x <= 3, x == 2, boolean variables like on1, true, false
Grouping: (φ)
No unbounded operators at all — the parser simply doesn't support G φ without [a, b]
One formula per line in a .stl file, # for comments

## SPOT setup
TODO
