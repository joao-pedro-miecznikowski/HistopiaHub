from flask import Flask, render_template, request, session, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy.orm import relationship
from datetime import datetime
import pytz
import uuid
import os

app = Flask(__name__)
app.secret_key = 'senha'
app.config['STATIC_FOLDER'] = 'static/'

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
EXPIRATION_TIME = 300

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha = db.Column(db.String(60), nullable=False)
    tipo = db.Column(db.CHAR(1), nullable=False, default='p')
    posts = db.relationship('Post', backref='author', lazy=True)

    def __repr__(self):
        return f"Usuario('{self.nome}', '{self.email}')"
    
class Categoria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False, unique=True)
    conteudos = db.relationship('Conteudo', backref='categoria', lazy=True)

    def __repr__(self):
        return f"Categoria('{self.nome}')"

class Conteudo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'), nullable=False)
    posts = db.relationship('Post', backref='conteudo', lazy=True)

    def __repr__(self):
        return f"Conteudo('{self.nome}', '{self.categoria.nome}')"

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    aprovado = db.Column(db.Boolean, default=False)
    editar = db.Column(db.Boolean, default=False)
    link_artigo = db.Column(db.String(100), nullable=False)
    link_jogo = db.Column(db.String(100), nullable=False)
    imagem_url = db.Column(db.String(255), nullable=False)
    data_publicacao = db.Column(db.DateTime, default=datetime.now(pytz.timezone('America/Sao_Paulo')))

    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'), nullable=False)
    conteudo_id = db.Column(db.Integer, db.ForeignKey('conteudo.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

    avaliacoes = db.relationship('Avaliacao', backref='post', lazy=True)
    notificacoes = db.relationship('Notificacao', backref='post', lazy=True, cascade="all, delete-orphan")

    def calcular_media_avaliacoes(self):
        if not self.avaliacoes:
            return 0
        total_nota = sum(avaliacao.nota for avaliacao in self.avaliacoes)
        media = total_nota / len(self.avaliacoes)
        return media

    def __repr__(self):
        return f"Post('{self.titulo}', '{self.conteudo.nome}')"

class Avaliacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nota = db.Column(db.Float, nullable=False)

    __table_args__ = (db.UniqueConstraint('post_id', 'usuario_id', name='uq_post_usuario'),)

    def __repr__(self):
        return f"Avaliacao(Post ID: '{self.post_id}', Usuario ID: '{self.usuario_id}', Nota: '{self.nota}')"
    
class Notificacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    tipo = db.Column(db.String(50), nullable=False) 
    motivo = db.Column(db.String(255), nullable=True)
    lida = db.Column(db.Boolean, default=False)
    data = db.Column(db.DateTime, default=datetime.now(pytz.timezone('America/Sao_Paulo')))

    usuario = db.relationship('Usuario', backref='notificacoes')

    def __repr__(self):
        return f"Notificacao('{self.tipo}', Post ID: '{self.post_id}', Usuario ID: '{self.usuario_id}')"

@app.route("/")
def tela_inicial():
    session.pop('_flashes', None)
    return render_template("tela_inicial.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('tela_inicial'))
    
    if request.method == "POST":
        email = request.form["email"]
        senha = request.form["senha"]

        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and check_password_hash(usuario.senha,senha):
            session['user_id'] = usuario.id
            session['logged_in'] = True
            session['user_email'] = email
            if usuario.tipo == 'a':
                session['is_admin'] = True

            return redirect(url_for('tela_inicial'))
        else:
            flash('E-mail ou senha inválidas')
            return render_template("login.html", error="E-mail ou senha inválidas")

    return render_template("login.html")

@app.route('/logout')
def logout():
    if 'logged_in' in session:
        session.clear()
        return redirect(url_for('tela_inicial'))

@app.route('/categorias')
def categorias():
    categorias = Categoria.query.all()

    return render_template("categorias.html", categorias=categorias)

@app.route('/categorias/<int:categoria_id>', methods=['GET'])
def conteudos(categoria_id):
    conteudos = Conteudo.query.filter_by(categoria_id=categoria_id).all()
    conteudo_selecionada = request.args.get('conteudo', 'Todos')

    if conteudo_selecionada != 'Todos':
        conteudo = Conteudo.query.filter_by(nome=conteudo_selecionada).first()
        if conteudo:
            posts = Post.query.filter_by(conteudo_id=conteudo.id, aprovado=True).all()  # Use conteudo_id aqui
        else:
            posts = []
    else:
        posts = Post.query.filter_by(categoria_id=categoria_id, aprovado=True).all()

    return render_template("conteudos.html", conteudos=conteudos, posts=posts, categoria_id=categoria_id)

@app.route('/categorias/<int:categoria_id>/editar_conteudos', methods=['GET', 'POST'])
def editar_conteudos(categoria_id):
    if not session.get('is_admin'):
        flash("Você não ter permissão para acessar essa página!")
        return redirect(url_for('tela_inicial'))
    
    conteudos = Conteudo.query.filter_by(categoria_id=categoria_id).all()

    if request.method == 'POST':
        if 'nome_conteudo' in request.form:
            nome_conteudo = request.form['nome_conteudo']
            nova_conteudo = Conteudo(nome=nome_conteudo, categoria_id=categoria_id)
            db.session.add(nova_conteudo)
            db.session.commit()
            flash('Conteudo adicionada com sucesso!', 'success')
            return redirect(url_for('editar_conteudos', categoria_id=categoria_id))

    return render_template("editar_conteudos.html", conteudos=conteudos, categoria_id=categoria_id)

@app.route('/remover_conteudo/<int:conteudo_id>', methods=['POST'])
def remover_conteudo(conteudo_id):
    if not session.get('is_admin'):
        flash("Você não ter permissão para acessar essa página!")
        return redirect(url_for('tela_inicial'))
    
    conteudo = Conteudo.query.get_or_404(conteudo_id)
    categoria_id = conteudo.categoria_id

    posts = Post.query.filter_by(conteudo=conteudo)

    for post in posts:
        os.remove(os.path.join(app.config['STATIC_FOLDER'], post.imagem_url))
    
    Post.query.filter_by(conteudo=conteudo).delete()

    db.session.delete(conteudo)
    db.session.commit()
    flash('Conteudo e seus posts removidos com sucesso!', 'success')
    return redirect(url_for('editar_conteudos', categoria_id=categoria_id))

@app.route('/conteudos/<int:categoria_id>', methods=['GET'])
def get_conteudos(categoria_id):
    conteudos = Conteudo.query.filter_by(categoria_id=categoria_id).all()
    return {'conteudos': [{ 'id': conteudo.id, 'nome': conteudo.nome } for conteudo in conteudos]}

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == "POST":
        try:
            nome = request.form["nome"]
            email = request.form["email"]
            senha = request.form["senha"]
            c_senha = request.form["c_senha"]

            if senha == c_senha:
                if Usuario.query.filter_by(email=email).first() is None:
                    usuario = Usuario(nome=nome, email=email, senha=generate_password_hash(senha))
                    db.session.add(usuario)
                    db.session.commit()
                    return redirect(url_for('login'))
                else:
                    flash('E-mail já cadastrado.')
                    return render_template("cadastro.html", error="E-mail já cadastrado.")
            else:
                flash('Senhas não coincidem.')
                return render_template("cadastro.html", error="Senhas não coincidem.")
        except KeyError as e:
            flash(f'Campo ausente: {str(e)}')
            return render_template("cadastro.html")
    
    return render_template("cadastro.html")

@app.route('/painel_usuario')
def painel_usuario():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    usuario = Usuario.query.filter_by(id=session['user_id']).first()

    return render_template("painel_usuario.html", usuario=usuario)

@app.route('/post/<int:post_id>')
def post(post_id):
    post = Post.query.filter_by(id=post_id).first()

    usuario = Usuario.query.filter_by(id=post.usuario_id).first()

    return render_template("post.html", post=post, usuario=usuario)

@app.route('/perfil/<int:user_id>')
def perfil_pessoal(user_id):
    usuario = Usuario.query.get_or_404(user_id)
    posts = Post.query.filter_by(usuario_id=user_id, aprovado=True).all()

    return render_template("perfil_pessoal.html", usuario=usuario, posts=posts)

@app.route('/editar_perfil', methods=['GET', 'POST'])
def editar_perfil():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    usuario = Usuario.query.get(session['user_id'])

    if request.method == 'POST':
        if 'atualizar_nome' in request.form:
            novo_nome = request.form.get('nome')
            usuario.nome = novo_nome
            db.session.commit()
            flash('Nome atualizado com sucesso!', 'success')

        elif 'atualizar_email' in request.form:
            senha = request.form.get('senha')
            novo_email = request.form.get('email')

            if not check_password_hash(usuario.senha, senha):
                flash('Senha incorreta. Não foi possível atualizar o e-mail.', 'danger')
            else:
                usuario.email = novo_email
                db.session.commit()
                flash('E-mail atualizado com sucesso!', 'success')

        elif 'atualizar_senha' in request.form:
            senha_antiga = request.form.get('senha_antiga')
            nova_senha = request.form.get('nova_senha')
            confirmacao_nova_senha = request.form.get('confirmacao_nova_senha')

            if not check_password_hash(usuario.senha, senha_antiga):
                flash('Senha antiga incorreta.', 'danger')
            elif nova_senha != confirmacao_nova_senha:
                flash('Nova senha e confirmação não coincidem.', 'danger')
            else:
                usuario.senha = generate_password_hash(nova_senha)
                db.session.commit()
                flash('Senha atualizada com sucesso!', 'success')

        return redirect(url_for('editar_perfil'))

    return render_template("editar_perfil.html", usuario=usuario)

@app.route('/criar_post', methods=['GET', 'POST'])
def criar_post():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    categorias = Categoria.query.all()
    conteudos = Conteudo.query.all()

    if request.method == 'POST':
        titulo = request.form['titulo']
        descricao = request.form['descricao']
        link_jogo = request.form['link_jogo']
        link_artigo = request.form['link_artigo']
        categoria_id = request.form['categoria']
        conteudo = request.form['conteudo']

        imagem = request.files.get('imagem')
        imagem_url = None
        
        if imagem and imagem.filename: 
            filename = secure_filename(imagem.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}" 
            imagem.save(os.path.join(app.config['STATIC_FOLDER']+'uploads/', unique_filename))
            imagem_url = f'uploads/{unique_filename}'

        if session.get('is_admin'):
            novo_post = Post(
                titulo=titulo,
                descricao=descricao,
                categoria_id=categoria_id,
                conteudo_id=conteudo,
                aprovado=True,
                link_jogo = link_jogo,
                link_artigo = link_artigo,
                usuario_id=session['user_id'],
                imagem_url=imagem_url
            )
        else:
            novo_post = Post(
                titulo=titulo,
                descricao=descricao,
                categoria_id=categoria_id,
                conteudo_id=conteudo,
                aprovado=False,
                link_jogo = link_jogo,
                link_artigo = link_artigo,
                usuario_id=session['user_id'],
                imagem_url=imagem_url
            )

        db.session.add(novo_post)
        db.session.commit()
        flash('Publicação criada e enviada para aprovação!', 'success')
        return redirect(url_for('tela_inicial'))

    return render_template('criar_post.html', categorias=categorias, conteudos=conteudos)

@app.route('/editar_post/<int:post_id>', methods=['GET', 'POST'])
def editar_post(post_id):
    post = Post.query.get_or_404(post_id)
    categorias = Categoria.query.all()
    conteudos = Conteudo.query.all()

    if request.method == 'POST':
        post.titulo = request.form['titulo']
        post.descricao = request.form['descricao']
        post.link_artigo = request.form['link_artigo']
        post.link_jogo = request.form['link_jogo']
        post.editar = False

        if session.get('is_admin'):
            post.aprovado = True
        else:
            post.aprovado = False

        imagem = request.files.get('imagem')

        # Verifica se uma nova imagem foi enviada
        if imagem and imagem.filename: 
            # Se uma nova imagem foi enviada, remove a imagem antiga
            if post.imagem_url:
                caminho_imagem_antiga = os.path.join(app.config['STATIC_FOLDER'], post.imagem_url)
                if os.path.exists(caminho_imagem_antiga):
                    os.remove(caminho_imagem_antiga)  # Remove a imagem antiga do sistema de arquivos

            # Salva a nova imagem
            filename = secure_filename(imagem.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}" 
            imagem.save(os.path.join(app.config['STATIC_FOLDER']+'uploads/', unique_filename))
            post.imagem_url = f'uploads/{unique_filename}'  # Atualiza a URL da imagem

        db.session.commit()
        flash('Post atualizado com sucesso!', 'success')
        return redirect(url_for('tela_inicial'))

    return render_template('editar_post.html', post=post, categorias=categorias, conteudos=conteudos)

@app.route('/remover_post/<int:post_id>', methods=['POST'])
def remover_post(post_id):
    post = Post.query.get_or_404(post_id)

    # Verifica se o usuário está logado e se é o autor do post ou um administrador
    if 'user_id' in session and (post.usuario_id == session['user_id'] or session.get('is_admin')):
        # Excluir notificações associadas ao post
        Notificacao.query.filter_by(post_id=post_id).delete()
        
        # Excluir avaliações associadas ao post
        Avaliacao.query.filter_by(post_id=post_id).delete()
        
        # Verifica se a imagem existe e a remove
        if post.imagem_url:
            # Constrói o caminho completo da imagem
            caminho_imagem = os.path.join(app.config['STATIC_FOLDER'], post.imagem_url)
            if os.path.exists(caminho_imagem):
                os.remove(caminho_imagem)  # Remove a imagem do sistema de arquivos

        db.session.delete(post)
        db.session.commit()
        flash('Post removido com sucesso!', 'success')
    else:
        flash('Você não tem permissão para remover este post.', 'danger')

    return redirect(url_for('tela_inicial'))  # Redireciona para a tela inicial ou outra página

@app.route('/avaliar_post/<int:post_id>', methods=['POST'])
def avaliar_post(post_id):
    if 'user_id' not in session:
        flash('Você precisa estar logado para avaliar um post.', 'danger')
        return redirect(url_for('login'))

    nota = request.form.get('nota')
    usuario_id = session['user_id']

    # Verifica se a avaliação já existe
    avaliacao_existente = Avaliacao.query.filter_by(post_id=post_id, usuario_id=usuario_id).first()
    if avaliacao_existente:
        flash('Você já avaliou este post.', 'danger')
        return redirect(url_for('post', post_id=post_id))

    # Cria uma nova avaliação
    nova_avaliacao = Avaliacao(post_id=post_id, usuario_id=usuario_id, nota=float(nota))
    db.session.add(nova_avaliacao)
    db.session.commit()

    flash('Avaliação registrada com sucesso!', 'success')
    return redirect(url_for('post', post_id=post_id))

@app.route('/posts_pendentes', methods=['GET', 'POST'])
def posts_pendentes():
    if not session.get('is_admin'):
        return redirect(url_for('tela_inicial'))

    post_pendente = Post.query.filter_by(aprovado=False, editar=False).order_by(Post.data_publicacao).first()

    if request.method == 'POST':
        if post_pendente:
            acao = request.form.get('acao')
            usuario_id = post_pendente.usuario_id

            if acao == 'aprovar':
                post_pendente.aprovado = True
                db.session.commit()

                notificacao = Notificacao(usuario_id=usuario_id, post_id=post_pendente.id, tipo='aprovação')
                db.session.add(notificacao)

                flash('Post aprovado com sucesso!', 'success')

            elif acao == 'reprovar':
                motivo = request.form.get('motivo')
                if motivo:
                    notificacao = Notificacao(usuario_id=usuario_id, post_id=post_pendente.id, tipo ='reprovação', motivo=motivo)
                    db.session.add(notificacao)

                    post_pendente.editar = True

                    flash(f'Post reprovado. Motivo: {motivo}', 'danger')
                else:
                    flash('Por favor, insira um motivo para a reprovação.', 'danger')

            db.session.commit()
            return redirect(url_for('posts_pendentes'))

    return render_template("posts_pendentes.html", post_pendente=post_pendente, Usuario=Usuario)

@app.route('/notificacoes')
def notificacoes():
    if 'user_id' not in session:
        return redirect(url_for('tela_inicial'))

    usuario_id = session['user_id']

    notificacoes = Notificacao.query.filter_by(usuario_id=usuario_id).order_by(Notificacao.data.desc(), Notificacao.id.desc())

    return render_template('notificacoes.html', notificacoes=notificacoes)

@app.route('/configuracoes')
def configuracoes():
    return render_template('configuracoes.html')

@app.route('/pesquisa', methods=['GET', 'POST'])
def pesquisa():
    query = request.args.get('query')
    resultados = []

    if query:
        # Realiza a busca de posts que contenham a query no título ou na descrição
        resultados = Post.query.filter(
            (Post.titulo.ilike(f'%{query}%')) | 
            (Post.descricao.ilike(f'%{query}%'))
        ).filter_by(aprovado=True).all()

    return render_template("pesquisa.html", query=query, resultados=resultados, Usuario=Usuario)

@app.before_request
def inicializar_categorias():
    categorias = ['6° ano','7° ano','8° ano','9° ano']
    
    for categoria_nome in categorias:
        if not Categoria.query.filter_by(nome=categoria_nome).first():
            nova_categoria = Categoria(nome=categoria_nome)
            db.session.add(nova_categoria)
    
    db.session.commit()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)