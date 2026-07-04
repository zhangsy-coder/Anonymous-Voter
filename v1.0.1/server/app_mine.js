const express = require("express")
const cors = require("cors")
const dotenv = require("dotenv")
dotenv.config()
const app = express()

app.use(cors())
app.use(express.json())

const authRoutes = require('./routes/auth')
const projectRoutes = require('./routes/project')
const userRoutes = require('./routes/user')
const candidateRoutes = require('./routes/candidate')
const voteRoutes = require('./routes/vote')
const { useReducer } = require("react")

app.use('/api/auth', authRoutes)
app.use('/api/prjects', projectRoutes)
app.use('/api/users', userRoutes)
app.use('/api/candidates', candidateRoutes)
app.use('/api/vote', voteRoutes)

const PORT = precess.env.PORT || 3000

app.listen(PORT, () => {
    console.log(`正在监听端口:${PORT}`)
})

