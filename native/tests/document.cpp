#include "grammar.h"

#include <iostream>
#include <iterator>

int main() {
    try {
        std::string source(std::istreambuf_iterator<char>(std::cin), {});
        std::cout << koine::document(source).dump() << '\n';
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
