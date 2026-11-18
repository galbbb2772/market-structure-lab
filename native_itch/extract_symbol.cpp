#include <array>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>

static uint16_t be16(const char* p) {
    return (static_cast<uint16_t>(static_cast<unsigned char>(p[0])) << 8)
         | static_cast<uint16_t>(static_cast<unsigned char>(p[1]));
}

static std::string trim_stock(const char* p, std::size_t n) {
    std::string s(p, p + n);
    while (!s.empty() && s.back() == ' ') s.pop_back();
    return s;
}

int main(int argc, char** argv) {
    std::string symbol = "SPCX";
    if (argc >= 2) symbol = argv[1];

    uint16_t target_locate = 0;
    bool found = false;
    uint64_t total_messages = 0;
    uint64_t kept_messages = 0;

    std::array<char, 2> prefix{};
    while (std::cin.read(prefix.data(), 2)) {
        const uint16_t len = be16(prefix.data());
        if (len == 0 || len > 4096) {
            std::cerr << "Invalid BinaryFile message length " << len
                      << " at message " << total_messages << "\n";
            return 2;
        }

        std::vector<char> msg(len);
        if (!std::cin.read(msg.data(), len)) {
            std::cerr << "Truncated payload at message " << total_messages << "\n";
            return 3;
        }
        ++total_messages;

        const char type = msg[0];

        // Stock Directory: symbol lives at payload offsets 11..18.
        if (type == 'R' && len >= 19) {
            const std::string stock = trim_stock(msg.data() + 11, 8);
            if (stock == symbol) {
                target_locate = be16(msg.data() + 1);
                found = true;
                std::cerr << "FOUND symbol=" << symbol
                          << " stock_locate=" << target_locate
                          << " message=" << total_messages << "\n";
            }
        }

        if (found && len >= 3 && be16(msg.data() + 1) == target_locate) {
            std::cout.write(prefix.data(), 2);
            std::cout.write(msg.data(), len);
            ++kept_messages;
        }

        if ((total_messages % 100000000ULL) == 0) {
            std::cerr << "scanned=" << total_messages
                      << " kept=" << kept_messages << "\n";
        }
    }

    if (!std::cin.eof()) {
        std::cerr << "Input stream failure before EOF\n";
        return 4;
    }
    if (!found) {
        std::cerr << "Target symbol " << symbol << " was not found in Stock Directory\n";
        return 5;
    }

    std::cerr << "DONE scanned=" << total_messages
              << " kept=" << kept_messages
              << " stock_locate=" << target_locate << "\n";
    return 0;
}
