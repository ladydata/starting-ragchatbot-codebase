import globals from 'globals';

export default [
    {
        languageOptions: {
            ecmaVersion: 2022,
            sourceType: 'module',
            globals: {
                ...globals.browser,
                marked: 'readonly',
            },
        },
        rules: {
            // Best practices
            eqeqeq: ['error', 'always'],
            'no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
            'no-console': ['warn', { allow: ['error', 'warn'] }],
            curly: ['error', 'all'],

            // Style consistency
            semi: ['error', 'always'],
            quotes: ['error', 'single', { avoidEscape: true }],
            indent: ['error', 4],
            'comma-dangle': ['error', 'always-multiline'],
            'no-trailing-spaces': 'error',
            'eol-last': ['error', 'always'],
            'no-multiple-empty-lines': ['error', { max: 1, maxEOF: 0 }],

            // ES6+
            'prefer-const': 'error',
            'no-var': 'error',
            'arrow-spacing': ['error', { before: true, after: true }],
            'object-shorthand': ['error', 'always'],
        },
    },
    {
        ignores: ['node_modules/', '*.min.js'],
    },
];
