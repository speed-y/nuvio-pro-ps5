// Host check: every requested code point is in at least one CJK face.
// The title does not ship this program. scripts/build.py compiles and runs it.
#include <ft2build.h>
#include FT_FREETYPE_H

#include <cstdint>
#include <cstdio>
#include <fstream>
#include <string>
#include <vector>

int main(int argc, char **argv)
{
    if (argc < 3)
    {
        std::fprintf(stderr, "usage: %s codepoints.txt font...\n", argv[0]);
        return 2;
    }
    FT_Library library = nullptr;
    if (FT_Init_FreeType(&library) != 0)
    {
        std::fprintf(stderr, "FreeType did not start\n");
        return 1;
    }
    std::vector<FT_Face> faces;
    for (int i = 2; i < argc; ++i)
    {
        FT_Face face = nullptr;
        if (FT_New_Face(library, argv[i], 0, &face) != 0)
        {
            std::fprintf(stderr, "cannot read %s\n", argv[i]);
            return 1;
        }
        faces.push_back(face);
    }
    std::ifstream input(argv[1]);
    std::string line;
    int total = 0;
    int missing = 0;
    while (std::getline(input, line))
    {
        if (line.empty())
            continue;
        ++total;
        const FT_ULong codepoint = static_cast<FT_ULong>(std::stoul(line, nullptr, 16));
        bool found = false;
        for (FT_Face face : faces)
        {
            if (FT_Get_Char_Index(face, codepoint) != 0)
            {
                found = true;
                break;
            }
        }
        if (!found)
        {
            ++missing;
            if (missing <= 20)
                std::fprintf(stderr, "missing U+%04lX\n", static_cast<unsigned long>(codepoint));
        }
    }
    std::printf("covered %d of %d\n", total - missing, total);
    for (FT_Face face : faces)
        FT_Done_Face(face);
    FT_Done_FreeType(library);
    return missing == 0 && total > 0 ? 0 : 1;
}
